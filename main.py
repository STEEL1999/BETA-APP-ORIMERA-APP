import os
import re
import time
import threading
from urllib.parse import urlparse
import flet as ft
import requests
import yt_dlp

def extract_pimpbunny_com(page_url):
    headers = {
        'Referer': page_url,
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36'
    }
    resp = requests.get(page_url, headers=headers, timeout=15)
    resp.raise_for_status()
    matches = re.findall(r'https?://pimpbunny\.com/[^\s"\'<>]+\.mp4(?:\?[^\s"\'<>]*)?', resp.text)
    if not matches:
        return None
    options = {}
    for url in set(matches):
        if any(x in url.lower() for x in ["preview", "screenshots", "thumbs"]):
            continue
        res_match = re.search(r'_(\d+p)\.mp4', url)
        if res_match:
            options[res_match.group(1)] = url
        elif "get_file" in url:
            options["Calidad Principal"] = url
    return options if options else None

CUSTOM_EXTRACTORS = {
    "pimpbunny.com": extract_pimpbunny_com,
    "www.pimpbunny.com": extract_pimpbunny_com
}

class DownloadWorker:
    def __init__(self, download_type, url, save_dir, title, card, page):
        self.download_type = download_type
        self.url = url
        self.save_dir = save_dir
        self.title = title
        self.card = card
        self.page = page
        self.is_paused = False
        self.is_cancelled = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def pause(self):
        self.is_paused = True
        self.card.update_status("Pausado", "0 KB/s")

    def resume(self):
        self.is_paused = False
        self.card.update_status("Descargando...", "Calculando...")

    def cancel(self):
        self.is_cancelled = True
        self.card.update_status("Cancelado", "-")

    def _format_speed(self, bps):
        if not bps or bps <= 0:
            return "0 KB/s"
        if bps >= 1024 * 1024:
            return f"{bps / (1024 * 1024):.2f} MB/s"
        return f"{bps / 1024:.1f} KB/s"

    def _run(self):
        try:
            if self.download_type in ("ytdlp", "stream"):
                self._download_ytdlp()
            else:
                self._download_direct()
        except Exception:
            if not self.is_cancelled:
                self.card.update_status("Error", "-")

    def _download_ytdlp(self):
        def hook(d):
            if self.is_cancelled:
                raise Exception("Cancelado")
            while self.is_paused:
                if self.is_cancelled:
                    raise Exception("Cancelado")
                time.sleep(0.5)
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed", 0)
                percent = (downloaded / total) if total > 0 else 0
                speed_str = self._format_speed(speed)
                self.card.update_progress(percent, speed_str)

        out_template = os.path.join(self.save_dir, "%(title)s.%(ext)s")
        ydl_opts = {
            "outtmpl": out_template,
            "format": "best",
            "merge_output_format": "mp4",
            "quiet": True,
            "progress_hooks": [hook],
            "nocheckcertificate": True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([self.url])
        if not self.is_cancelled:
            self.card.complete_download()

    def _download_direct(self):
        clean_title = re.sub(r'[\\/*?:"<>|]', "_", self.title)
        if not clean_title.endswith(".mp4"):
            clean_title += ".mp4"
        filepath = os.path.join(self.save_dir, clean_title)
        downloaded = 0
        mode = "wb"
        if os.path.exists(filepath):
            downloaded = os.path.getsize(filepath)
            mode = "ab"

        headers = {}
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"

        with requests.get(self.url, headers=headers, stream=True, timeout=30) as r:
            if r.status_code not in (200, 206):
                downloaded = 0
                mode = "wb"
                r = requests.get(self.url, stream=True, timeout=30)
            
            total = int(r.headers.get("content-length", 0)) + downloaded
            last_time = time.time()
            last_downloaded = downloaded

            with open(filepath, mode) as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if self.is_cancelled:
                        f.close()
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        raise Exception("Cancelado")
                    while self.is_paused:
                        if self.is_cancelled:
                            f.close()
                            if os.path.exists(filepath):
                                os.remove(filepath)
                            raise Exception("Cancelado")
                        time.sleep(0.5)
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        curr_time = time.time()
                        if curr_time - last_time >= 0.5:
                            speed = (downloaded - last_downloaded) / (curr_time - last_time)
                            percent = (downloaded / total) if total > 0 else 0
                            self.card.update_progress(percent, self._format_speed(speed))
                            last_time = curr_time
                            last_downloaded = downloaded
        if not self.is_cancelled:
            self.card.complete_download()

class DownloadCard(ft.Card):
    def __init__(self, title, page):
        self.page_ref = page
        self.lbl_title = ft.Text(title, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSE)
        self.lbl_speed = ft.Text("0 KB/s", size=12, color=ft.Colors.GREY_400)
        self.lbl_status = ft.Text("Iniciando...", size=12, color=ft.Colors.BLUE_200)
        self.progress_bar = ft.ProgressBar(value=0, color=ft.Colors.GREEN_400)
        self.btn_pause = ft.IconButton(
            icon=ft.Icons.PAUSE,
            icon_color=ft.Colors.ORANGE_300,
            on_click=self.toggle_pause
        )
        self.btn_cancel = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_color=ft.Colors.RED_400,
            on_click=self.cancel
        )
        self.worker = None

        super().__init__(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(content=self.lbl_title, expand=True),
                        self.btn_pause,
                        self.btn_cancel,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.progress_bar,
                    ft.Row([
                        self.lbl_status,
                        self.lbl_speed,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ]),
                padding=10
            )
        )

    def set_worker(self, worker):
        self.worker = worker

    def toggle_pause(self, e):
        if not self.worker:
            return
        if self.worker.is_paused:
            self.worker.resume()
            self.btn_pause.icon = ft.Icons.PAUSE
        else:
            self.worker.pause()
            self.btn_pause.icon = ft.Icons.PLAY_ARROW
        self.page_ref.update()

    def cancel(self, e):
        if not self.worker:
            return
        self.worker.cancel()
        self.btn_pause.disabled = True
        self.btn_cancel.disabled = True
        self.page_ref.update()

    def update_progress(self, val, speed_text):
        self.progress_bar.value = val
        self.lbl_speed.value = speed_text
        self.lbl_status.value = "Descargando..."
        self.page_ref.update()

    def update_status(self, status_text, speed_text):
        self.lbl_status.value = status_text
        self.lbl_speed.value = speed_text
        self.page_ref.update()

    def complete_download(self):
        self.progress_bar.value = 1.0
        self.lbl_status.value = "Completado"
        self.lbl_speed.value = "-"
        self.btn_pause.disabled = True
        self.btn_cancel.disabled = True
        self.page_ref.update()

def main(page: ft.Page):
    page.title = "Snaptube Flet Android"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    downloads_list = ft.ListView(expand=True, spacing=10, padding=10)

    bs = ft.BottomSheet(
        ft.Container(
            ft.Column([
                ft.Row([
                    ft.Text("Cola de Descargas", weight=ft.FontWeight.BOLD, size=16),
                    ft.IconButton(icon=ft.Icons.KEYBOARD_ARROW_DOWN, on_click=lambda _: page.close(bs))
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(),
                downloads_list
            ]),
            padding=15,
            height=350
        ),
        open=False
    )
    page.overlay.append(bs)

    url_input = ft.TextField(
        value="https://www.google.com",
        hint_text="Buscar o ingresar URL...",
        expand=True,
        border_radius=20,
        content_padding=10
    )
    
    if hasattr(ft, "WebView"):
        web_view_control = ft.WebView(url="https://www.google.com", expand=True)
    else:
        web_view_control = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.PUBLIC, size=64, color=ft.Colors.BLUE),
                ft.Text("Navegador Web Listo", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("Ingresa una URL o enlace directo arriba para descargar.", color=ft.Colors.GREY_400)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
            alignment=ft.Alignment(0, 0)
        )

    def navigate(e):
        target = url_input.value.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            target = f"https://www.google.com/search?q={target}" if "." not in target else f"https://{target}"
        url_input.value = target
        
        if hasattr(web_view_control, 'url'):
            web_view_control.url = target
        page.update()

    def open_downloads(e):
        page.open(bs)

    def trigger_download(e):
        current_url = url_input.value.strip()
        domain = urlparse(current_url).netloc.lower()

        if domain in CUSTOM_EXTRACTORS:
            res = CUSTOM_EXTRACTORS[domain](current_url)
            if res:
                start_download_process("direct", list(res.values())[0], "Video_Pimpbunny")
                return

        def async_extract():
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
                    info = ydl.extract_info(current_url, download=False)
                    if info:
                        title = info.get('title', 'Video_Descargado')
                        start_download_process("ytdlp", current_url, title)
            except Exception:
                pass

        threading.Thread(target=async_extract, daemon=True).start()

    def start_download_process(download_type, url, title):
        save_dir = "/sdcard/Download" if os.path.exists("/sdcard/Download") else os.path.expanduser("~/Downloads")
        card = DownloadCard(title, page)
        worker = DownloadWorker(download_type, url, save_dir, title, card, page)
        card.set_worker(worker)
        downloads_list.controls.insert(0, card)
        page.open(bs)
        page.update()
        worker.start()

    page.add(
        ft.Column([
            ft.Container(
                content=ft.Row([
                    url_input,
                    ft.IconButton(icon=ft.Icons.SEARCH, on_click=navigate),
                    ft.IconButton(icon=ft.Icons.DOWNLOAD, icon_color=ft.Colors.GREEN_ACCENT, on_click=trigger_download),
                    ft.IconButton(icon=ft.Icons.FOLDER_SPECIAL, on_click=open_downloads)
                ]),
                padding=8,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
            ),
            web_view_control
        ], expand=True)
    )

ft.app(target=main)

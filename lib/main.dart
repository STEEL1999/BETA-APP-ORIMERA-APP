import 'dart:io';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:dio/dio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Navegador & Descargador',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true),
      home: const BrowserScreen(),
    );
  }
}

class BrowserScreen extends StatefulWidget {
  const BrowserScreen({super.key});

  @override
  State<BrowserScreen> createState() => _BrowserScreenState();
}

class _BrowserScreenState extends State<BrowserScreen> {
  late final WebViewController _controller;
  final TextEditingController _urlController = TextEditingController(text: "https://www.google.com");
  String currentUrl = "https://www.google.com";
  int progress = 0;
  bool isDownloading = false;

  @override
  void initState() {
    super.initState();
    _requestPermissions();

    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (int progressValue) {
            setState(() {
              progress = progressValue;
            });
          },
          onPageStarted: (String url) {
            setState(() {
              currentUrl = url;
              _urlController.text = url;
            });
          },
        ),
      )
      ..loadRequest(Uri.parse('https://www.google.com'));
  }

  Future<void> _requestPermissions() async {
    await Permission.storage.request();
  }

  void _loadUrl(String url) {
    String formattedUrl = url.trim();
    if (!formattedUrl.startsWith("http://") && !formattedUrl.startsWith("https://")) {
      if (formattedUrl.contains(".") && !formattedUrl.contains(" ")) {
        formattedUrl = "https://$formattedUrl";
      } else {
        formattedUrl = "https://www.google.com/search?q=$formattedUrl";
      }
    }
    _controller.loadRequest(Uri.parse(formattedUrl));
  }

  Future<void> _downloadCurrentPageOrMedia() async {
    final status = await Permission.storage.request();
    if (status.isGranted) {
      try {
        setState(() {
          isDownloading = true;
        });

        final externalDir = await getExternalStorageDirectory();
        final fileName = "download_${DateTime.now().millisecondsSinceEpoch}.html";
        final savePath = "${externalDir?.path ?? '/sdcard/Download'}/$fileName";

        Dio dio = Dio();
        await dio.download(currentUrl, savePath);

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Descargado con éxito en: $savePath')),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Error al descargar el archivo')),
          );
        }
      } finally {
        if (mounted) {
          setState(() {
            isDownloading = false;
          });
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8.0),
          child: TextField(
            controller: _urlController,
            decoration: InputDecoration(
              hintText: "Buscar o escribir URL...",
              contentPadding: const EdgeInsets.symmetric(horizontal: 15, vertical: 8),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(30),
                borderSide: BorderSide.none,
              ),
              filled: true,
              fillColor: Colors.grey[800],
            ),
            onSubmitted: _loadUrl,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.arrow_forward_outlined),
            onPressed: () => _loadUrl(_urlController.text),
          ),
          IconButton(
            icon: isDownloading 
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.download, color: Colors.greenAccent),
            onPressed: isDownloading ? null : _downloadCurrentPageOrMedia,
          ),
        ],
      ),
      body: Column(
        children: [
          if (progress < 100)
            LinearProgressIndicator(value: progress / 100, color: Colors.blueAccent),
          Expanded(
            child: WebViewWidget(controller: _controller),
          ),
        ],
      ),
      bottomNavigationBar: BottomAppBar(
        height: 50,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            IconButton(
              icon: const Icon(Icons.arrow_back),
              onPressed: () async {
                if (await _controller.canGoBack()) {
                  await _controller.goBack();
                }
              },
            ),
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: () => _controller.reload(),
            ),
            IconButton(
              icon: const Icon(Icons.arrow_forward),
              onPressed: () async {
                if (await _controller.canGoForward()) {
                  await _controller.goForward();
                }
              },
            ),
          ],
        ),
      ),
    );
  }
}

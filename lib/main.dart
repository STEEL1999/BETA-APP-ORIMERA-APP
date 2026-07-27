import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:flutter_downloader/flutter_downloader.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await FlutterDownloader.initialize(debug: true, ignoreSsl: true);
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
  InAppWebViewController? webViewController;
  final TextEditingController _urlController = TextEditingController(text: "https://www.google.com");
  String currentUrl = "https://www.google.com";
  double progress = 0;

  @override
  void initState() {
    super.initState();
    _requestPermissions();
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
    webViewController?.loadUrl(urlRequest: URLRequest(url: WebUri(formattedUrl)));
  }

  Future<void> _downloadCurrentPageOrMedia() async {
    final status = await Permission.storage.request();
    if (status.isGranted) {
      final externalDir = await getExternalStorageDirectory();
      final downloadPath = externalDir?.path ?? "/sdcard/Download";

      await FlutterDownloader.enqueue(
        url: currentUrl,
        savedDir: downloadPath,
        showNotification: true,
        openFileFromNotification: true,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Iniciando descarga en segundo plano...')),
        );
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
            icon: const Icon(Icons.download, color: Colors.greenAccent),
            onPressed: _downloadCurrentPageOrMedia,
          ),
        ],
      ),
      body: Column(
        children: [
          if (progress < 1.0)
            LinearProgressIndicator(value: progress, color: Colors.blueAccent),
          Expanded(
            child: InAppWebView(
              initialUrlRequest: URLRequest(url: WebUri("https://www.google.com")),
              onWebViewCreated: (controller) {
                webViewController = controller;
              },
              onLoadStart: (controller, url) {
                setState(() {
                  currentUrl = url.toString();
                  _urlController.text = currentUrl;
                });
              },
              onProgressChanged: (controller, progressValue) {
                setState(() {
                  progress = progressValue / 100;
                });
              },
            ),
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
              onPressed: () => webViewController?.goBack(),
            ),
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: () => webViewController?.reload(),
            ),
            IconButton(
              icon: const Icon(Icons.arrow_forward),
              onPressed: () => webViewController?.goForward(),
            ),
          ],
        ),
      ),
    );
  }
}

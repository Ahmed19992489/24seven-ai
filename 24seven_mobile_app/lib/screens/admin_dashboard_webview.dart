import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'login_screen.dart';

class AdminDashboardWebView extends StatefulWidget {
  const AdminDashboardWebView({super.key});

  @override
  State<AdminDashboardWebView> createState() => _AdminDashboardWebViewState();
}

class _AdminDashboardWebViewState extends State<AdminDashboardWebView> {
  late final WebViewController _controller;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0x00000000))
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (int progress) {
            // Update loading bar.
          },
          onPageStarted: (String url) {
            setState(() {
              _isLoading = true;
            });
          },
          onPageFinished: (String url) {
            setState(() {
              _isLoading = false;
            });
          },
          onWebResourceError: (WebResourceError error) {
            debugPrint('WebView Error: ${error.description}');
          },
        ),
      )
      ..loadRequest(Uri.parse('https://24seven-ai.com/admin-crm.html'));
  }

  void _logout() async {
    if (mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => const LoginScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = Theme.of(context).colorScheme.primary;

    return WillPopScope(
      onWillPop: () async {
        if (await _controller.canGoBack()) {
          _controller.goBack();
          return false;
        }
        return true;
      },
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: Colors.white,
          title: const Text(
            'لوحة الإدارة الشاملة (CRM)',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.black87),
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.refresh, color: Colors.blue),
              onPressed: () => _controller.reload(),
            ),
            IconButton(
              icon: const Icon(Icons.logout, color: Colors.red),
              onPressed: _logout,
            ),
          ],
        ),
        body: Stack(
          children: [
            WebViewWidget(controller: _controller),
            if (_isLoading)
              Container(
                color: Colors.white.withOpacity(0.8),
                child: Center(
                  child: SpinKitFadingCircle(
                    color: primaryColor,
                    size: 50.0,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

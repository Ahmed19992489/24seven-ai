import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'screens/login_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Supabase with your existing project credentials
  await Supabase.initialize(
    url: 'https://khskudtxbypohvnreloi.supabase.co',
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I',
  );

  runApp(const SevenLimousineApp());
}

class SevenLimousineApp extends StatelessWidget {
  const SevenLimousineApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '24Seven Limousine',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6366F1), // Indigo
          primary: const Color(0xFF6366F1),
          secondary: const Color(0xFFF59E0B), // Amber
        ),
        fontFamily: 'Roboto', // We can load Arabic fonts later like 'Cairo'
        useMaterial3: true,
      ),
      home: const LoginScreen(),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'captain_dashboard.dart';
import 'client_dashboard.dart';
import 'admin_dashboard_webview.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _supabase = Supabase.instance.client;
  
  // Controllers
  final TextEditingController _clientPhoneController = TextEditingController();
  final TextEditingController _captainPhoneController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _isLoading = false;
  String _errorMessage = '';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _clientPhoneController.dispose();
    _captainPhoneController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _showError(String message) {
    setState(() {
      _errorMessage = message;
      _isLoading = false;
    });
  }

  // --- CLIENT LOGIN (Phone Number) ---
  Future<void> _loginAsClient() async {
    final phone = _clientPhoneController.text.trim();
    if (phone.isEmpty || phone.length < 10) {
      _showError('الرجاء إدخال رقم هاتف صحيح');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    final fakeEmail = '$phone@24seven-client.app';
    final password = phone.substring(phone.length - 6);

    try {
      // 1. Attempt to login
      final response = await _supabase.auth.signInWithPassword(
        email: fakeEmail,
        password: password,
      );

      if (response.session != null) {
        _navigateToDashboard(const ClientDashboard(), 'client', phone);
      }
    } on AuthException catch (e) {
      // 2. If user doesn't exist, sign up
      if (e.message.contains('Invalid login credentials') || e.message.contains('Email not confirmed')) {
        try {
          // Lookup real name from existing google_reservations if any
          String realName = 'عميل ${phone.substring(phone.length - 4)}';
          final reservations = await _supabase
              .from('google_reservations')
              .select('customer_name')
              .or('customer_phone.ilike.%$phone%')
              .order('created_at', ascending: false)
              .limit(1);

          if (reservations.isNotEmpty && reservations[0]['customer_name'] != null) {
            realName = reservations[0]['customer_name'];
          }

          // Sign Up
          final signUpRes = await _supabase.auth.signUp(
            email: fakeEmail,
            password: password,
            data: {'full_name': realName, 'role': 'client'},
          );

          if (signUpRes.session != null) {
            _navigateToDashboard(const ClientDashboard(), 'client', phone);
          } else {
            _showError('تم إرسال رابط تأكيد الحساب لبريدك الإلكتروني');
          }
        } catch (signUpErr) {
          _showError('خطأ أثناء إنشاء الحساب الجديد: ${signUpErr.toString()}');
        }
      } else {
        _showError('فشل تسجيل الدخول: ${e.message}');
      }
    } catch (err) {
      _showError('حدث خطأ غير متوقع: $err');
    }
  }

  // --- CAPTAIN LOGIN (Phone Number) ---
  Future<void> _loginAsCaptain() async {
    final phone = _captainPhoneController.text.trim();
    if (phone.isEmpty) {
      _showError('الرجاء إدخال رقم الهاتف');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      // Query the drivers table directly to see if registered
      final data = await _supabase
          .from('drivers')
          .select('*')
          .eq('phone', phone)
          .maybeSingle();

      if (data == null) {
        _showError('رقم الهاتف هذا غير مسجل ككابتن. تواصل مع الإدارة.');
        return;
      }

      // Navigate to captain dashboard
      _navigateToDashboard(CaptainDashboard(driverData: data), 'captain', phone);
    } catch (err) {
      _showError('خطأ في الاتصال بقاعدة البيانات: $err');
    }
  }

  // --- ADMIN/MODERATOR LOGIN (Email/Password) ---
  Future<void> _loginAsAdmin() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text.trim();

    if (email.isEmpty || password.isEmpty) {
      _showError('الرجاء إدخال البريد الإلكتروني وكلمة المرور');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final response = await _supabase.auth.signInWithPassword(
        email: email,
        password: password,
      );

      if (response.session != null) {
        final profile = await _supabase
            .from('profiles')
            .select('full_name, role')
            .eq('id', response.user!.id)
            .maybeSingle();

        if (profile != null) {
          final role = profile['role'] ?? 'admin';
          if (role == 'admin' || role == 'moderator' || role == 'staff') {
            _navigateToDashboard(const AdminDashboardWebView(), role, email);
          } else {
            _navigateToDashboard(const ClientDashboard(), role, email);
          }
        } else {
          _showError('الملف الشخصي غير موجود');
        }
      }
    } catch (err) {
      _showError('فشل تسجيل الدخول: $err');
    }
  }

  void _navigateToDashboard(Widget screen, String role, String identifier) {
    setState(() {
      _isLoading = false;
    });
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (context) => screen),
    );
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = Theme.of(context).colorScheme.primary;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Logo/Icon
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: primaryColor.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.local_taxi,
                  size: 40,
                  color: primaryColor,
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                '24Seven Limousine',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF1E293B),
                ),
              ),
              const Text(
                'تطبيق العملاء والكباتن الموحد',
                style: TextStyle(
                  fontSize: 14,
                  color: Color(0xFF64748B),
                ),
              ),
              const SizedBox(height: 32),

              // TabBar Card
              Card(
                elevation: 4,
                shadowColor: Colors.black12,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Container(
                  width: double.infinity,
                  constraints: const BoxConstraints(maxWidth: 400),
                  padding: const EdgeInsets.all(20.0),
                  child: Column(
                    children: [
                      TabBar(
                        controller: _tabController,
                        labelColor: primaryColor,
                        unselectedLabelColor: const Color(0xFF64748B),
                        indicatorColor: primaryColor,
                        indicatorSize: TabBarIndicatorSize.tab,
                        tabs: const [
                          Tab(text: 'عميل'),
                          Tab(text: 'كابتن'),
                          Tab(text: 'إدارة'),
                        ],
                      ),
                      const SizedBox(height: 24),
                      
                      if (_errorMessage.isNotEmpty) ...[
                        Text(
                          _errorMessage,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.red,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],

                      // TabViews
                      SizedBox(
                        height: 200,
                        child: TabBarView(
                          controller: _tabController,
                          children: [
                            // Client Tab
                            _buildPhoneField(
                              controller: _clientPhoneController,
                              hint: 'أدخل رقم هاتف العميل',
                              icon: Icons.phone_android,
                            ),
                            // Captain Tab
                            _buildPhoneField(
                              controller: _captainPhoneController,
                              hint: 'أدخل رقم هاتف الكابتن المسجل',
                              icon: Icons.drive_eta,
                            ),
                            // Admin Tab
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                _buildTextField(
                                  controller: _emailController,
                                  hint: 'البريد الإلكتروني',
                                  icon: Icons.email,
                                  isEmail: true,
                                ),
                                const SizedBox(height: 12),
                                _buildTextField(
                                  controller: _passwordController,
                                  hint: 'كلمة المرور',
                                  icon: Icons.lock,
                                  isPassword: true,
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Submit Button
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton(
                          onPressed: _isLoading ? null : () {
                            if (_tabController.index == 0) {
                              _loginAsClient();
                            } else if (_tabController.index == 1) {
                              _loginAsCaptain();
                            } else {
                              _loginAsAdmin();
                            }
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: primaryColor,
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                            elevation: 0,
                          ),
                          child: _isLoading
                              ? const SpinKitThreeBounce(
                                  color: Colors.white,
                                  size: 20,
                                )
                              : const Text(
                                  'تسجيل الدخول',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPhoneField({
    required TextEditingController controller,
    required String hint,
    required IconData icon,
  }) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _buildTextField(
          controller: controller,
          hint: hint,
          icon: icon,
          isPhone: true,
        ),
      ],
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String hint,
    required IconData icon,
    bool isPhone = false,
    bool isEmail = false,
    bool isPassword = false,
  }) {
    return TextField(
      controller: controller,
      obscureText: isPassword,
      keyboardType: isPhone
          ? TextInputType.phone
          : isEmail
              ? TextInputType.emailAddress
              : TextInputType.text,
      textAlign: isPhone ? TextAlign.left : TextAlign.right,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Color(0xFF94A3B8), fontSize: 14),
        prefixIcon: Icon(icon, color: const Color(0xFF64748B)),
        filled: true,
        fillColor: const Color(0xFFF1F5F9),
        contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: Theme.of(context).colorScheme.primary, width: 2),
        ),
      ),
    );
  }
}

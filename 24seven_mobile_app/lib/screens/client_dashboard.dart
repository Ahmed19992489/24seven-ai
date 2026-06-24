import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong2.dart';
import 'login_screen.dart';

class ClientDashboard extends StatefulWidget {
  const ClientDashboard({super.key});

  @override
  State<ClientDashboard> createState() => _ClientDashboardState();
}

class _ClientDashboardState extends State<ClientDashboard> {
  final _supabase = Supabase.instance.client;
  bool _isLoading = false;
  List<Map<String, dynamic>> _myReservations = [];
  
  // Active User Info
  String _clientPhone = '';
  String _clientName = '';

  // Form Fields
  final TextEditingController _pickupController = TextEditingController();
  final TextEditingController _dropoffController = TextEditingController();
  final TextEditingController _notesController = TextEditingController();
  DateTime _selectedDate = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _selectedTime = const TimeOfDay(hour: 12, minute: 0);

  String _selectedCarType = 'سيدان اقتصادية';
  String _selectedTripType = 'مطار القاهرة';
  String _selectedPaymentMethod = 'كاش للكابتن';
  int _passengers = 1;
  int _bags = 0;

  // Estimated Price Calculation
  int get _estimatedPrice {
    int base = 500;
    if (_selectedCarType.contains('SUV')) base = 850;
    if (_selectedCarType.contains('فان')) base = 1200;
    if (_selectedTripType.contains('ذهاب وعودة')) base = (base * 1.8).round();
    return base;
  }

  @override
  void initState() {
    super.initState();
    _fetchUserInfoAndTrips();
  }

  @override
  void dispose() {
    _pickupController.dispose();
    _dropoffController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _fetchUserInfoAndTrips() async {
    setState(() {
      _isLoading = true;
    });

    final user = _supabase.auth.currentUser;
    if (user == null) return;

    // Email format: phone@24seven-client.app
    final email = user.email ?? '';
    _clientPhone = email.split('@')[0];
    _clientName = user.userMetadata?['full_name'] ?? 'عميل ليموزين';

    try {
      // Fetch reservations matching the client phone suffix
      final phoneSuffix = _clientPhone.substring(_clientPhone.length - 9);
      final reservations = await _supabase
          .from('google_reservations')
          .select('*')
          .or('customer_phone.ilike.%$phoneSuffix%,whatsapp_num.ilike.%$phoneSuffix%')
          .order('created_at', ascending: false);

      setState(() {
        _myReservations = List<Map<String, dynamic>>.from(reservations);
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('خطأ في تحميل الحجوزات: $e')),
      );
    }
  }

  Future<void> _createNewBooking() async {
    final pickup = _pickupController.text.trim();
    final dropoff = _dropoffController.text.trim();

    if (pickup.isEmpty || dropoff.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('⚠️ يرجى إدخال عنوان نقطة الالتقاء والوصول')),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    final dateStr = '${_selectedDate.year}-${_selectedDate.month.toString().padLeft(2, '0')}-${_selectedDate.day.toString().padLeft(2, '0')}';
    final timeStr = '${_selectedTime.hour.toString().padLeft(2, '0')}:${_selectedTime.minute.toString().padLeft(2, '0')}';

    final payload = {
      'customer_name': _clientName,
      'customer_phone': _clientPhone,
      'whatsapp_num': _clientPhone,
      'client_status': 'قديم',
      'car_type': _selectedCarType,
      'trip_type': _selectedTripType,
      'passengers': _passengers,
      'bags': _bags,
      'trip_date': dateStr,
      'trip_time': timeStr,
      'pickup_address': pickup,
      'dropoff_address': dropoff,
      'cost': _estimatedPrice,
      'notes': _notesController.text.trim(),
      'status': 'pending',
      'payment_method': _selectedPaymentMethod,
    };

    try {
      await _supabase.from('google_reservations').insert(payload);
      
      _pickupController.clear();
      _dropoffController.clear();
      _notesController.clear();

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('🎉 تم تسجيل الحجز بنجاح ومراجعته من الإدارة!')),
      );
      
      _fetchUserInfoAndTrips();
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('فشل حجز الرحلة: $e')),
      );
    }
  }

  void _logout() async {
    await _supabase.auth.signOut();
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

    return DefaultTabController(
      length: 2,
      child: Scaffold(
        backgroundColor: const Color(0xFFF8FAFC),
        appBar: AppBar(
          backgroundColor: Colors.white,
          title: Text(
            'أهلاً، $_clientName',
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
          ),
          bottom: TabBar(
            labelColor: primaryColor,
            unselectedLabelColor: Colors.grey,
            indicatorColor: primaryColor,
            tabs: const [
              Tab(text: 'حجز رحلة جديدة', icon: Icon(Icons.add_location_alt)),
              Tab(text: 'رحلاتي الحالية', icon: Icon(Icons.history)),
            ],
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.logout, color: Colors.red),
              onPressed: _logout,
            ),
          ],
        ),
        body: _isLoading
            ? Center(
                child: SpinKitFadingCircle(
                  color: primaryColor,
                  size: 50.0,
                ),
              )
            : TabBarView(
                children: [
                  // Tab 1: Create Booking Form
                  SingleChildScrollView(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Map Section (Mocking GPS picking)
                        Container(
                          height: 180,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(20),
                            color: Colors.grey.shade200,
                          ),
                          clipBehavior: Clip.antiAlias,
                          child: FlutterMap(
                            options: const MapOptions(
                              initialCenter: LatLng(30.0444, 31.2357), // Cairo Center
                              initialZoom: 13.0,
                            ),
                            children: [
                              TileLayer(
                                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                                userAgentPackageName: 'com.example.app',
                              ),
                              const MarkerLayer(
                                markers: [
                                  Marker(
                                    point: LatLng(30.0444, 31.2357),
                                    child: Icon(Icons.my_location, color: Colors.blue, size: 30),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 20),

                        // Form card
                        Card(
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                          elevation: 2,
                          child: Padding(
                            padding: const EdgeInsets.all(16.0),
                            child: Column(
                              children: [
                                _buildInputField('من (نقطة الالتقاء)', _pickupController, Icons.trip_origin, Colors.green),
                                const SizedBox(height: 12),
                                _buildInputField('إلى (نقطة الوصول)', _dropoffController, Icons.location_on, Colors.red),
                                const SizedBox(height: 16),
                                
                                // DateTime row
                                Row(
                                  children: [
                                    Expanded(
                                      child: OutlinedButton.icon(
                                        onPressed: () async {
                                          final d = await showDatePicker(
                                            context: context,
                                            initialDate: _selectedDate,
                                            firstDate: DateTime.now(),
                                            lastDate: DateTime.now().add(const Duration(days: 30)),
                                          );
                                          if (d != null) setState(() => _selectedDate = d);
                                        },
                                        icon: const Icon(Icons.date_range),
                                        label: Text('${_selectedDate.year}-${_selectedDate.month}-${_selectedDate.day}'),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: OutlinedButton.icon(
                                        onPressed: () async {
                                          final t = await showTimePicker(
                                            context: context,
                                            initialTime: _selectedTime,
                                          );
                                          if (t != null) setState(() => _selectedTime = t);
                                        },
                                        icon: const Icon(Icons.access_time),
                                        label: Text(_selectedTime.format(context)),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 16),

                                // Dropdowns
                                _buildDropdown('نوع السيارة', _selectedCarType, [
                                  'سيدان اقتصادية',
                                  'سيدان VIP (مرسيدس)',
                                  'سيارة عائلية SUV',
                                  'فان سياحي (H1)'
                                ], (v) => setState(() => _selectedCarType = v!)),
                                const SizedBox(height: 12),
                                
                                _buildDropdown('نوع الخدمة', _selectedTripType, [
                                  'مطار القاهرة',
                                  'ليموزين بين المحافظات',
                                  'مشوار داخل القاهرة',
                                  'عرض اليوم الكامل'
                                ], (v) => setState(() => _selectedTripType = v!)),
                                const SizedBox(height: 12),

                                _buildDropdown('طريقة الدفع', _selectedPaymentMethod, [
                                  'كاش للكابتن',
                                  'فودافون كاش',
                                  'بطاقة ائتمانية (أونلاين)'
                                ], (v) => setState(() => _selectedPaymentMethod = v!)),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 20),

                        // Pricing Estimate card
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.indigo.shade50,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: Colors.indigo.shade100),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text('السعر التقديري للرحلة', style: TextStyle(fontWeight: FontWeight.bold)),
                              Text(
                                '$_estimatedPrice ج.م',
                                style: const TextStyle(fontWeight: FontWeight.black, fontSize: 18, color: Colors.indigo),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),

                        ElevatedButton(
                          onPressed: _createNewBooking,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: primaryColor,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                          ),
                          child: const Text('تأكيد وحجز الرحلة', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        ),
                      ],
                    ),
                  ),

                  // Tab 2: List of active/previous trips
                  RefreshIndicator(
                    onRefresh: _fetchUserInfoAndTrips,
                    child: _myReservations.isEmpty
                        ? const Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.history_toggle_off, size: 64, color: Colors.grey),
                                SizedBox(height: 16),
                                Text('لا توجد رحلات سابقة مسجلة', style: TextStyle(color: Colors.grey)),
                              ],
                            ),
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.all(16),
                            itemCount: _myReservations.length,
                            itemBuilder: (context, index) {
                              final res = _myReservations[index];
                              return _buildReservationCard(res);
                            },
                          ),
                  ),
                ],
              ),
      ),
    );
  }

  Widget _buildInputField(String label, TextEditingController controller, IconData icon, Color color) {
    return TextField(
      controller: controller,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, color: color),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  Widget _buildDropdown(String label, String value, List<String> items, ValueChanged<String?> onChanged) {
    return DropdownButtonFormField<String>(
      value: value,
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
      items: items.map((i) => DropdownMenuItem(value: i, child: Text(i))).toList(),
      onChanged: onChanged,
    );
  }

  Widget _buildReservationCard(Map<String, dynamic> res) {
    final pickup = res['pickup_address'] ?? 'غير محدد';
    final dropoff = res['dropoff_address'] ?? 'غير محدد';
    final date = res['trip_date'] ?? '--';
    final time = res['trip_time'] ?? '--';
    final cost = res['cost'] ?? 0;
    final status = res['status'] ?? 'pending';

    Color statusColor = Colors.orange;
    String statusText = 'قيد المراجعة';
    if (status == 'arrived') {
      statusColor = Colors.blue;
      statusText = 'الكابتن وصل';
    } else if (status == 'active') {
      statusColor = Colors.green;
      statusText = 'في الطريق';
    } else if (status == 'completed' || status == 'trip_ended') {
      statusColor = Colors.grey;
      statusText = 'مكتملة';
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('📅 $date  ⏰ $time', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: statusColor),
                  ),
                  child: Text(
                    statusText,
                    style: TextStyle(color: statusColor, fontSize: 12, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const Divider(height: 24),
            Row(
              children: [
                const Icon(Icons.circle, color: Colors.green, size: 12),
                const SizedBox(width: 8),
                Expanded(child: Text('من: $pickup', style: const TextStyle(fontSize: 13))),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.location_on, color: Colors.red, size: 12),
                const SizedBox(width: 8),
                Expanded(child: Text('إلى: $dropoff', style: const TextStyle(fontSize: 13))),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('السيارة: ${res['car_type'] ?? '--'}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                Text('$cost ج.م', style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.indigo, fontSize: 15)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

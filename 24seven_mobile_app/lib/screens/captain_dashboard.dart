import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:url_launcher/url_launcher.dart';
import 'login_screen.dart';

class CaptainDashboard extends StatefulWidget {
  final Map<String, dynamic> driverData;
  const CaptainDashboard({super.key, required this.driverData});

  @override
  State<CaptainDashboard> createState() => _CaptainDashboardState();
}

class _CaptainDashboardState extends State<CaptainDashboard> {
  final _supabase = Supabase.instance.client;
  bool _isLoading = false;
  List<Map<String, dynamic>> _trips = [];
  List<Map<String, dynamic>> _sheetTrips = [];

  @override
  void initState() {
    super.initState();
    _loadTrips();
  }

  Future<void> _loadTrips() async {
    setState(() {
      _isLoading = true;
    });

    final driverId = widget.driverData['id'];
    final driverPhone = widget.driverData['phone'].toString().replaceAll(RegExp(r'\D'), '');
    
    // Egyptian phone formatting logic for google_reservations lookup
    String phoneSuffix = driverPhone;
    if (phoneSuffix.startsWith('0020')) phoneSuffix = phoneSuffix.substring(4);
    else if (phoneSuffix.startsWith('20') && phoneSuffix.length > 10) phoneSuffix = phoneSuffix.substring(2);
    if (phoneSuffix.startsWith('0') && phoneSuffix.length == 11) phoneSuffix = phoneSuffix.substring(1);
    
    final phoneSuffixMatch = phoneSuffix.length > 8 ? phoneSuffix.substring(phoneSuffix.length - 9) : phoneSuffix;
    final withZero = '0$phoneSuffix';
    final with20 = '20$phoneSuffix';

    try {
      // 1. Fetch from trips table
      final tripsData = await _supabase
          .from('trips')
          .select('*, cars:cars!fk_trips_car(*)')
          .eq('driver_id', driverId)
          .inFilter('status', ['driver_assigned', 'completed', 'trip_ended', 'arrived', 'active'])
          .order('created_at', ascending: false);

      // 2. Fetch from google_reservations table
      final sheetTripsData = await _supabase
          .from('google_reservations')
          .select('*')
          .or('modified_driver_phone.ilike.%$phoneSuffixMatch%,modified_driver_phone.eq.$withZero,modified_driver_phone.eq.$with20,modified_driver_phone.eq.$phoneSuffix')
          .order('trip_date', ascending: false)
          .limit(30);

      setState(() {
        _trips = List<Map<String, dynamic>>.from(tripsData);
        _sheetTrips = List<Map<String, dynamic>>.from(sheetTripsData);
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('خطأ في تحميل الرحلات: $e')),
      );
    }
  }

  Future<void> _updateTripStatus(String table, String id, String currentStatus) async {
    String newStatus = '';
    if (currentStatus == 'driver_assigned' || currentStatus == 'pending') {
      newStatus = 'arrived';
    } else if (currentStatus == 'arrived') {
      newStatus = 'active';
    } else if (currentStatus == 'active') {
      newStatus = 'completed';
    }

    if (newStatus.isEmpty) return;

    setState(() {
      _isLoading = true;
    });

    try {
      await _supabase.from(table).update({'status': newStatus}).eq('id', id);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('✅ تم تحديث حالة الرحلة بنجاح!')),
      );
      _loadTrips();
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('فشل التحديث: $e')),
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
    final driverName = widget.driverData['name'] ?? 'كابتن';
    final primaryColor = Theme.of(context).colorScheme.primary;

    return Scaffold(
      backgroundColor: const Color(0xFFF1F5F9),
      appBar: AppBar(
        backgroundColor: Colors.white,
        title: Text(
          'كابتن $driverName',
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.blue),
            onPressed: _loadTrips,
          ),
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
          : RefreshIndicator(
              onRefresh: _loadTrips,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Header Stats
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [primaryColor, primaryColor.withOpacity(0.8)],
                        ),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Column(
                        children: [
                          const Text(
                            'إجمالي رحلاتك اليوم',
                            style: TextStyle(color: Colors.white70, fontSize: 14),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '${_trips.length + _sheetTrips.length}',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 36,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    const Text(
                      'الرحلات المسندة إليك',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF1E293B),
                      ),
                    ),
                    const SizedBox(height: 12),

                    if (_trips.isEmpty && _sheetTrips.isEmpty)
                      const Card(
                        child: Padding(
                          padding: EdgeInsets.symmetric(vertical: 40.0),
                          child: Column(
                            children: [
                              Icon(Icons.inbox, size: 48, color: Colors.grey),
                              SizedBox(height: 12),
                              Text('لا توجد رحلات مسندة حالياً', style: TextStyle(color: Colors.grey)),
                            ],
                          ),
                        ),
                      )
                    else ...[
                      // Core Trips
                      ..._trips.map((t) => _buildTripCard(t, 'trips')),
                      // Google Sheet Reservations
                      ..._sheetTrips.map((t) => _buildTripCard(t, 'google_reservations')),
                    ],
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildTripCard(Map<String, dynamic> trip, String sourceTable) {
    final isSheet = sourceTable == 'google_reservations';
    final tripId = trip['id'].toString();
    final clientName = trip['customer_name'] ?? 'عميل ليموزين';
    final clientPhone = trip['customer_phone'] ?? '';
    final pickup = trip['pickup_address'] ?? 'غير محدد';
    final dropoff = trip['dropoff_address'] ?? 'غير محدد';
    final date = isSheet ? (trip['trip_date'] ?? '--') : (trip['created_at'].toString().split('T')[0]);
    final time = isSheet ? (trip['trip_time'] ?? '--') : '--';
    final price = trip['cost'] ?? 0;
    final status = trip['status'] ?? 'pending';

    Color statusColor = Colors.orange;
    String statusText = 'معلقة';
    if (status == 'arrived') {
      statusColor = Colors.blue;
      statusText = 'وصل الكابتن';
    } else if (status == 'active') {
      statusColor = Colors.green;
      statusText = 'قيد التنفيذ';
    } else if (status == 'completed' || status == 'trip_ended') {
      statusColor = Colors.grey;
      statusText = 'منتهية';
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Row 1: Client Name and Status Badge
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  clientName,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
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

            // Pickup & Dropoff Address
            Row(
              children: [
                const Icon(Icons.circle, color: Colors.green, size: 14),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('من: $pickup', style: const TextStyle(fontSize: 13)),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.location_on, color: Colors.red, size: 14),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('إلى: $dropoff', style: const TextStyle(fontSize: 13)),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Date, Time, Cost Info
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('📅 $date  ⏰ $time', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                Text(
                  '$price ج.م',
                  style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.indigo, fontSize: 16),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Action Buttons
            Row(
              children: [
                if (clientPhone.isNotEmpty)
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => launchUrl(Uri.parse('tel:$clientPhone')),
                      icon: const Icon(Icons.call, size: 16),
                      label: const Text('اتصال بالعميل', style: TextStyle(fontSize: 12)),
                      style: OutlinedButton.styleFrom(
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ),
                if (clientPhone.isNotEmpty) const SizedBox(width: 8),
                
                // Status action button
                if (status != 'completed' && status != 'trip_ended')
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () => _updateTripStatus(sourceTable, tripId, status),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.indigo,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      child: Text(
                        status == 'driver_assigned' || status == 'pending'
                            ? 'وصلت للعميل'
                            : status == 'arrived'
                                ? 'بدء الرحلة'
                                : 'إنهاء الرحلة',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

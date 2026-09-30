// OsokaiApi — single place all mobile screens talk to backend.
// One global Backend URL + Auth Token (Settings tab), sent on every call.
import 'dart:convert';
import 'package:http/http.dart' as http;

class OsokaiApi {
  static String base = const String.fromEnvironment('API_BASE_URL', defaultValue: 'http://127.0.0.1:8765');
  static String token = '';

  static void configure(String b, String t) {
    if (b.trim().isNotEmpty) base = b.trim();
    token = t.trim();
  }

  static Map<String, String> get _h => {
        'Content-Type': 'application/json',
        if (token.isNotEmpty) 'Authorization': 'Bearer $token',
      };

  static Future<Map<String, dynamic>> _get(String p) async {
    final r = await http.get(Uri.parse('$base$p'), headers: _h);
    if (r.statusCode == 401) throw Exception('wrong Osok-AI token — paste it in Settings');
    if (r.statusCode != 200) throw Exception('GET $p -> ${r.statusCode}');
    return jsonDecode(r.body);
  }

  static Future<Map<String, dynamic>> _post(String p, [Map<String, dynamic>? b]) async {
    final r = await http.post(Uri.parse('$base$p'), headers: _h, body: jsonEncode(b ?? {}));
    if (r.statusCode == 401) throw Exception('wrong Osok-AI token — paste it in Settings');
    if (r.statusCode != 200) throw Exception('POST $p -> ${r.statusCode}');
    return jsonDecode(r.body);
  }

  static Future<Map<String, dynamic>> health() async {
    final r = await http.get(Uri.parse('$base/health'));
    return jsonDecode(r.body);
  }
  static Future<Map<String, dynamic>> authCheck() => _get('/auth-check');
  static Future<Map<String, dynamic>> chat(String message) async {
    final j = await _post('/chat', {'message': message, 'device': 'mobile-flutter'});
    return j;
  }
  static Future<List> files([String sub = '']) async {
    final j = await _get(sub.isEmpty ? '/files' : '/files?path=${Uri.encodeComponent(sub)}');
    if (j['entries'] != null) return j['entries'] as List;
    return (j['workspace'] as List).map((n) => {'name': n, 'dir': false}).toList();
  }
  static Future<List> approvals() async {
    final j = await _get('/approvals');
    return j['pending'] as List;
  }
  static Future<Map<String, dynamic>> resolveApproval(int id, bool allow) =>
      _post('/approvals/$id/resolve', {'allow': allow});
  static Future<Map<String, dynamic>> tasks() => _get('/tasks');
  static Future<List> connectors() async {
    final j = await _get('/connectors');
    return j['connectors'] as List;
  }
  static Future<Map<String, dynamic>> connectorConnect(String id, String tok) =>
      _post('/connectors/$id/connect', {'token': tok});
  static Future<Map<String, dynamic>> connectorDisconnect(String id) =>
      _post('/connectors/$id/disconnect');
  static Future<Map<String, dynamic>> connectorSetEnabled(String id, bool enabled) async {
    final r = await http.patch(Uri.parse('$base/connectors/$id'), headers: _h, body: jsonEncode({'enabled': enabled}));
    if (r.statusCode == 401) throw Exception('wrong Osok-AI token — paste it in Settings');
    if (r.statusCode != 200) throw Exception('PATCH /connectors/$id -> ${r.statusCode}');
    return jsonDecode(r.body);
  }
  static Future<Map<String, dynamic>> inbox() => _get('/inbox');
  static Future<Map<String, dynamic>> months() => _get('/history/months');
  static Future<Map<String, dynamic>> month(String ym) => _get('/history?month=$ym');
}

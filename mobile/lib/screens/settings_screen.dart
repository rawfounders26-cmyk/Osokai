// SettingsScreen — sync + per-service connectors. Explicit dark colors (visible on black).
import 'package:flutter/material.dart';
import '../api.dart';

const _bg = Color(0xFF000000);
const _card = Color(0xFF14141B);
const _line = Color(0xFF26262E);
const _txt = Color(0xFFE8E8EE);
const _sub = Color(0xFF8A8A96);
const _purple = Color(0xFF5B5BD6);
const _green = Color(0xFF22C55E);

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override State<SettingsScreen> createState() => _S();
}

class _S extends State<SettingsScreen> {
  List conns = [];
  final baseCtrl = TextEditingController();
  final tokCtrl = TextEditingController();
  final svcCtrl = TextEditingController();
  String live = '';
  @override void initState() { super.initState(); _load(); }
  @override void dispose() { baseCtrl.dispose(); tokCtrl.dispose(); svcCtrl.dispose(); super.dispose(); }

  Future<void> _load() async {
    try {
      final c = await OsokaiApi.connectors();
      if (mounted) setState(() => conns = c);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('offline: $e')));
    }
  }

  InputDecoration _box(String hint) => InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: _sub),
        filled: true,
        fillColor: _card,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: _line)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: _purple)),
      );

  bool isOn(String id) {
    for (final c in conns) { if (c is Map && c['id'] == id) return c['connected'] == true; }
    return false;
  }

  String _statusText(Map c) {
    if (c['enabled'] != true) return 'Off';
    if (c['status'] == 'connected') return '${c['unread_count'] ?? 0} unread';
    return 'Not connected';
  }

  Color _colorFor(Map c) {
    final h = (c['color'] ?? '#5B5BD6').toString().replace('#', '');
    try {
      return Color(int.parse('FF$h', radix: 16));
    } catch (_) {
      return _purple;
    }
  }

  Future<void> _toggle(String id) async {
    if (isOn(id)) {
      await OsokaiApi.connectorDisconnect(id);
      _load();
      return;
    }
    final ctrl = TextEditingController();
    final token = await showDialog<String>(
        context: context,
        builder: (_) => AlertDialog(
              backgroundColor: _card,
              title: Text('Connect ${id[0].toUpperCase()}${id.substring(1)}', style: const TextStyle(color: _txt)),
              content: TextField(controller: ctrl, style: const TextStyle(color: _txt),
                  decoration: _box('paste service token')),
              actions: [
                TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
                TextButton(onPressed: () => Navigator.pop(context, ctrl.text), child: const Text('Connect')),
              ],
            ));
    if (token != null && token.isNotEmpty) {
      await OsokaiApi.connectorConnect(id, token);
      _load();
    }
  }

  @override Widget build(BuildContext context) {
    const all = ['gmail', 'outlook', 'whatsapp', 'discord', 'slack'];
    return Container(
      color: _bg,
      child: ListView(padding: const EdgeInsets.only(bottom: 16), children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 14, 16, 4),
          child: Text('Settings — sync', style: TextStyle(color: _txt, fontSize: 20, fontWeight: FontWeight.bold)),
        ),
        Padding(padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: TextField(controller: baseCtrl, style: const TextStyle(color: _txt), decoration: _box('Backend URL (e.g. http://10.0.0.5:8765)'))),
        Padding(padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
            child: TextField(controller: tokCtrl, obscureText: true, style: const TextStyle(color: _txt), decoration: _box('Osok-AI auth token'))),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: SizedBox(
            height: 48,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: _purple, foregroundColor: Colors.white, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
              onPressed: () async {
                OsokaiApi.configure(baseCtrl.text, tokCtrl.text);
                try {
                  await OsokaiApi.authCheck();
                  setState(() => live = 'live + synced ✓');
                  _load();
                } catch (e) {
                  setState(() => live = '$e');
                }
              },
              child: const Text('CONNECT', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ),
        if (live.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Text(live, style: TextStyle(color: live.contains('✓') ? _green : Colors.redAccent)),
          ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 18, 16, 4),
          child: Text('Connectors', style: TextStyle(color: _txt, fontSize: 16, fontWeight: FontWeight.bold)),
        ),
        for (final c in conns)
          InkWell(
            onTap: () => _toggle(c['id']),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: _line))),
              child: Row(children: [
                Container(
                  width: 38, height: 38,
                  decoration: BoxDecoration(color: _colorFor(c), borderRadius: BorderRadius.circular(19)),
                  alignment: Alignment.center,
                  child: Text((c['name'] ?? '?').toString().substring(0, 1),
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 17)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(c['name'] ?? c['id'], style: const TextStyle(color: _txt, fontSize: 15)),
                    Text(_statusText(c), style: const TextStyle(color: _sub, fontSize: 12)),
                  ]),
                ),
                if ((c['unread_count'] ?? 0) > 0)
                  Container(
                    margin: const EdgeInsets.only(right: 8),
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(color: Colors.redAccent, borderRadius: BorderRadius.circular(11)),
                    child: Text('${c['unread_count']}', style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold)),
                  ),
                Switch(
                  value: c['enabled'] == true,
                  onChanged: (v) async {
                    setState(() => c['enabled'] = v);
                    try {
                      await OsokaiApi.connectorSetEnabled(c['id'], v);
                    } catch (e) {
                      setState(() => c['enabled'] = !v);
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
                    }
                  },
                ),
              ]),
            ),
          ),
        InkWell(
          onTap: () => ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('More connectors coming next'))),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: _line))),
            child: const Row(children: [
              Icon(Icons.add_circle_outline, color: _sub),
              SizedBox(width: 12),
              Expanded(child: Text('Add more (+)', style: TextStyle(color: _txt, fontSize: 15))),
            ]),
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 14, 16, 0),
          child: Text('Desktop shortcut: Alt+Space / Option+Space', style: TextStyle(color: _sub, fontSize: 12)),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
          child: Text('API: ${OsokaiApi.base}', style: const TextStyle(color: _sub, fontSize: 12)),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: OutlinedButton(
            style: OutlinedButton.styleFrom(foregroundColor: _txt, side: const BorderSide(color: _line), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
            onPressed: _load,
            child: const Text('REFRESH'),
          ),
        ),
      ]),
    );
  }
}

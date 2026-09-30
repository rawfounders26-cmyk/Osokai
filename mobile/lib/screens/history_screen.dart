// HistoryScreen — Monthly AI Usage + month folders (past/current/upcoming auto-flow).
import 'package:flutter/material.dart';
import '../api.dart';

const _colors = [0xFFE5484D, 0xFF46A758, 0xFFF5C518, 0xFF8E4EC6, 0xFF3E63DD, 0xFFE09342];

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});
  @override State<HistoryScreen> createState() => _H();
}

class _H extends State<HistoryScreen> {
  Map<String, dynamic>? data;
  String? openYm;
  Map<String, dynamic>? detail;
  Future<void> _load() async {
    try {
      final d = await OsokaiApi.months();
      if (mounted) setState(() => data = d);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('offline: $e')));
    }
  }
  Future<void> _open(Map<String, dynamic> m) async {
    if (openYm == m['month']) { setState(() => openYm = null); return; }
    setState(() => openYm = m['month'] as String);
    try {
      final d = await OsokaiApi.month(m['month'] as String);
      if (mounted) setState(() => detail = d);
    } catch (e) {
      if (mounted) setState(() => detail = m);
    }
  }
  @override void initState() { super.initState(); _load(); }
  @override Widget build(BuildContext context) {
    if (data == null) {
      return const Center(child: Text('loading usage…', style: TextStyle(color: Colors.grey)));
    }
    final week = (data!['week'] as List).cast<Map<String, dynamic>>();
    final maxD = week.map((d) => d['tasks'] as int).fold(1, (a, b) => a > b ? a : b);
    final months = (data!['months'] as List).cast<Map<String, dynamic>>();
    final best = data!['best_day'] as Map<String, dynamic>;
    return Container(
      color: Colors.black,
      child: RefreshIndicator(
        onRefresh: _load,
        child: ListView(padding: const EdgeInsets.only(bottom: 120), children: [
          Padding(
            padding: const EdgeInsets.all(14),
            child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: const [
              Text('Monthly\nAI Usage', style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
              Icon(Icons.close, color: Colors.grey),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            child: Text('${data!['total_tasks']} goals', style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.bold)),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            child: Text('Highest day: ${best['day']} (${best['tasks']})', style: const TextStyle(color: Colors.grey, fontSize: 12)),
          ),
          Container(
            margin: const EdgeInsets.all(14),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: const Color(0xFF101014), borderRadius: BorderRadius.circular(14)),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (final d in week)
                  Column(children: [
                    Container(
                      width: 22,
                      height: 8 + (90 * (d['tasks'] as int) / maxD),
                      decoration: BoxDecoration(
                        color: (d['tasks'] == maxD && (d['tasks'] as int) > 0)
                            ? const Color(0xFFF5C518)
                            : const Color(0xFF2C2C36),
                        borderRadius: BorderRadius.circular(6),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text((d['day'] as String).substring(0, 3), style: const TextStyle(color: Colors.grey, fontSize: 10)),
                  ]),
              ],
            ),
          ),
          for (int i = 0; i < months.length; i++) ...[
            GestureDetector(
              onTap: () => _open(months[i]),
              child: Container(
                margin: EdgeInsets.only(left: 14, right: 14, top: i == 0 ? 8 : -44, bottom: 12),
                padding: const EdgeInsets.all(14),
                constraints: const BoxConstraints(minHeight: 108),
                decoration: BoxDecoration(
                  color: Color(_colors[i % _colors.length]),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${months[i]['label']}${months[i]['current'] == true ? ' • now' : ''}${months[i]['upcoming'] == true ? ' • soon' : ''}',
                      style: const TextStyle(color: Color(0xFF111111), fontSize: 16, fontWeight: FontWeight.bold)),
                  Text('${months[i]['usage']}', style: const TextStyle(color: Color(0xFF222222), fontSize: 12)),
                ]),
              ),
            ),
            if (openYm == months[i]['month'])
              Container(
                margin: const EdgeInsets.only(left: 14, right: 14, top: -6, bottom: 12),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: const Color(0xFF14141B), borderRadius: BorderRadius.circular(12)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final g in ((detail != null && detail!['month'] == months[i]['month'] ? detail!['goals'] : months[i]['goals']) as List))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('• ${g['text']}', style: const TextStyle(color: Color(0xFFE8E8EE), fontSize: 13)),
                      ),
                    if (((detail != null && detail!['month'] == months[i]['month'] ? detail!['goals'] : months[i]['goals']) as List).isEmpty)
                      const Text('no goals yet', style: TextStyle(color: Color(0xFFE8E8EE), fontSize: 13)),
                  ],
                ),
              ),
          ],
        ]),
      ),
    );
  }
}

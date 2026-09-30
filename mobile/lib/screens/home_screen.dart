// HomeScreen — dashboard: backend /health + /inbox + running tasks.
import 'package:flutter/material.dart';
import '../api.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override State<HomeScreen> createState() => _H();
}

class _H extends State<HomeScreen> {
  String status = 'loading…';
  String briefing = '';
  int running = 0;
  @override void initState() { super.initState(); _load(); }
  Future<void> _load() async {
    try {
      final h = await OsokaiApi.health();
      final inbox = await OsokaiApi.inbox();
      final t = await OsokaiApi.tasks();
      setState(() {
        status = (h['ok'] == true) ? 'backend online' : 'backend error';
        briefing = (inbox['summary']?['briefing'] ?? '').toString();
        running = ((t['running'] ?? []) as List).length;
      });
    } catch (e) { setState(() => status = 'backend offline: $apiBase'); }
  }
  @override Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: _load,
    child: ListView(padding: const EdgeInsets.all(16), children: [
      Text('Osok-AI Home', style: Theme.of(context).textTheme.headlineSmall),
      Text(status),
      const SizedBox(height: 12),
      Card(child: ListTile(title: const Text('Morning briefing'), subtitle: Text(briefing.isEmpty ? '—' : briefing))),
      Card(child: ListTile(title: const Text('Running tasks'), trailing: Text('$running'))),
    ]),
  );
}

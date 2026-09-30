// ChatScreen — YouTube opens in the app, everything else runs on the shared VM.
// Payment/sensitive goals show inline Approve/Reject cards (same as extension popup).
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});
  @override State<ChatScreen> createState() => _C();
}

class _C extends State<ChatScreen> {
  final ctrl = TextEditingController();
  final msgs = <Map<String, dynamic>>[];
  bool busy = false;

  Future<void> _open(String url) async {
    final u = Uri.parse(url);
    if (await canLaunchUrl(u)) await launchUrl(u, mode: LaunchMode.externalApplication);
  }

  Future<void> send() async {
    final text = ctrl.text.trim();
    if (text.isEmpty || busy) return;
    setState(() { msgs.add({'who': 'you', 'text': text}); busy = true; });
    ctrl.clear();
    try {
      final j = await OsokaiApi.chat(text);
      if (j['action'] == 'youtube_play' && (j['url'] ?? '').isNotEmpty) {
        _open(j['url']); // direct app, like mobile should
      }
      setState(() => msgs.add({
            'who': 'Osok-AI',
            'text': j['reply'] ?? '',
            'approval': j['approval_required'] == true ? j['approval_id'] : null,
            'kind': j['kind'] ?? '',
            'link': (j['action'] == 'open_url' || j['action'] == 'shop_browse') ? j['url'] : null,
          }));
    } catch (e) {
      setState(() => msgs.add({'who': 'Osok-AI', 'text': 'backend offline: $e'}));
    }
    setState(() => busy = false);
  }

  Future<void> _decide(Map m, bool allow) async {
    try {
      await OsokaiApi.resolveApproval(m['approval'], allow);
      setState(() {
        m['approval'] = null;
        m['text'] = '${m['text']}\n${allow ? 'Approved ✓' : 'Rejected'}';
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override Widget build(BuildContext context) => Column(children: [
        Expanded(
          child: ListView.builder(
            itemCount: msgs.length,
            itemBuilder: (_, i) {
              final m = msgs[i];
              if (m['who'] == 'you') {
                return Align(
                  alignment: Alignment.centerRight,
                  child: Container(
                    margin: const EdgeInsets.all(8),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(color: const Color(0xFF5B5BD6), borderRadius: BorderRadius.circular(16)),
                    child: Text(m['text'], style: const TextStyle(color: Colors.white)),
                  ),
                );
              }
              return Card(
                margin: const EdgeInsets.all(8),
                color: const Color(0xFF14141B),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(m['text'] ?? '', style: const TextStyle(color: Color(0xFFE8E8EE))),
                    if (m['link'] != null)
                      TextButton(onPressed: () => _open(m['link']), child: const Text('Open in browser ↗')),
                    if (m['approval'] != null) ...[
                      const SizedBox(height: 8),
                      Text(m['kind'] == 'payment' ? '💳 Payment approval — approve?' : "Approval #${m['approval']} — approve?",
                          style: const TextStyle(color: Colors.orange, fontWeight: FontWeight.bold)),
                      Row(children: [
                        TextButton(onPressed: () => _decide(m, true), child: const Text('Approve')),
                        TextButton(onPressed: () => _decide(m, false), child: const Text('Reject')),
                      ]),
                    ],
                  ]),
                ),
              );
            },
          ),
        ),
        Row(children: [
          Expanded(
              child: TextField(
                  controller: ctrl,
                  decoration: const InputDecoration(hintText: 'Give Osok-AI a goal…'))),
          IconButton(icon: const Icon(Icons.send), onPressed: send),
        ]),
      ]);
}

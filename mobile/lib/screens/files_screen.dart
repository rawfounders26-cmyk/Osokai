// FilesScreen — SAME VM store the agent saves to. Folders navigate, back goes up.
import 'package:flutter/material.dart';
import '../api.dart';

class FilesScreen extends StatefulWidget {
  const FilesScreen({super.key});
  @override State<FilesScreen> createState() => _F();
}

class _F extends State<FilesScreen> {
  List entries = [];
  String path = '';
  String err = '';
  @override void initState() { super.initState(); _load(''); }
  Future<void> _load(String p) async {
    try {
      setState(() { entries = []; err = ''; });
      final f = await OsokaiApi.files(p);
      setState(() { entries = f; path = p; });
    } catch (e) {
      setState(() => err = 'backend offline: $e');
    }
  }
  void _up() {
    if (path.isEmpty) return;
    final parts = path.split('/')..removeWhere((e) => e.isEmpty)..removeLast();
    _load(parts.join('/'));
  }
  @override Widget build(BuildContext context) => RefreshIndicator(
        onRefresh: () => _load(path),
        child: err.isNotEmpty
            ? ListView(children: [ListTile(title: Text(err))])
            : ListView.builder(
                itemCount: entries.length + (path.isEmpty ? 0 : 1),
                itemBuilder: (_, i) {
                  if (path.isNotEmpty && i == 0) {
                    return ListTile(leading: const Icon(Icons.arrow_upward), title: Text('/$path'), subtitle: const Text('tap to go up'), onTap: _up);
                  }
                  final e = entries[path.isEmpty ? i : i - 1];
                  final isDir = e['dir'] == true;
                  return ListTile(
                    leading: Icon(isDir ? Icons.folder : Icons.insert_drive_file,
                        color: isDir ? Colors.amber : null),
                    title: Text('${e['name']}'),
                    onTap: isDir ? () => _load(path.isEmpty ? e['name'] : '$path/${e['name']}') : null,
                  );
                },
              ),
      );
}

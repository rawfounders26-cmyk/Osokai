// Osok-AI mobile shell — floating pill nav (Home/History/Files/Settings + Chat circle).
import 'package:flutter/material.dart';
import 'screens/home_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/files_screen.dart';
import 'screens/history_screen.dart';
import 'screens/settings_screen.dart';

void main() => runApp(const OsokaiApp());

class OsokaiApp extends StatefulWidget {
  const OsokaiApp({super.key});
  @override State<OsokaiApp> createState() => _Shell();
}

class _Shell extends State<OsokaiApp> {
  int nav = 0; // 0-3 pill (Home/History/Files/Settings), 4 = Chat (+)
  static const _screens = [0, 3, 2, 4, 1]; // nav -> screen index

  Widget _pillBtn(int k, IconData icon) {
    final on = nav == k;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => nav = k),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: on ? const Color(0xFF4B4B9E) : Colors.transparent,
            borderRadius: BorderRadius.circular(24),
          ),
          child: Icon(icon, color: on ? const Color(0xFFCFCFFF) : const Color(0xFF7A7A8A), size: 26),
        ),
      ),
    );
  }

  @override Widget build(BuildContext context) {
    const screens = [HomeScreen(), ChatScreen(), FilesScreen(), HistoryScreen(), SettingsScreen()];
    final int screenIdx = _screens[nav];
    return MaterialApp(
      title: 'Osok-AI',
      theme: ThemeData.dark(),
      home: Scaffold(
        backgroundColor: Colors.black,
        body: Stack(children: [
          Padding(padding: const EdgeInsets.only(bottom: 108), child: SafeArea(child: screens[screenIdx])),
          Positioned(
            bottom: 0, left: 0, right: 0,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(18, 6, 18, 22),
              child: Row(children: [
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(color: const Color(0xFF17171F).withOpacity(0.92), borderRadius: BorderRadius.circular(30)),
                    child: Row(
                      children: [
                        _pillBtn(0, Icons.home_outlined),
                        _pillBtn(1, Icons.access_time_outlined),
                        _pillBtn(2, Icons.folder_outlined),
                        _pillBtn(3, Icons.settings_outlined),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                GestureDetector(
                  onTap: () => setState(() => nav = 4),
                  child: Container(
                    width: 60, height: 60,
                    decoration: BoxDecoration(
                        color: nav == 4 ? const Color(0xFF5D5DC4) : const Color(0xFF4B4B9E),
                        borderRadius: BorderRadius.circular(30)),
                    child: const Icon(Icons.add, color: Color(0xFFCFCFFF), size: 30),
                  ),
                ),
              ]),
            ),
          ),
        ]),
      ),
    );
  }
}

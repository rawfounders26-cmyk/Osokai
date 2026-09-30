// Osok-AI Home — 4 cards. Bill Split opens the splitter; others jump to tabs.
import { useState, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, RefreshControl } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect, router } from 'expo-router';
import { billGroups, notifications, pendingApprovals, loopsDue, nudges, usageSummary } from '../services/api';import { colors, radius, spacing } from '../services/theme';

const CARDS = [
  { id: 'bills', title: 'Bill Split', emoji: '🧾', bg: '#0ea5a4', route: '/bill' },
  { id: 'outfit', title: 'Outfit Planner', emoji: '👕', bg: '#8e4ec6', route: '/outfit' },
  { id: 'loops', title: 'Agent Loop', emoji: '🔁', bg: '#6366f1', route: '/loops' },
  { id: 'connect', title: 'Connectors', emoji: '🔗', bg: '#e5484d', route: '/connectors' },
];

export default function DashboardScreen() {
  const insets = useSafeAreaInsets();
  const [due, setDue] = useState('');
  const [alerts, setAlerts] = useState([]);
  const [spend, setSpend] = useState('');
  const [ref, setRef] = useState(false);

  const load = useCallback(async () => {
    try {
      const g = await billGroups();
      let owe = 0, owed = 0;
      for (const grp of g.groups || []) {
        for (const d of grp.balances || []) {
          if (d.from === 'Me') owe += d.amount;
          if (d.to === 'Me') owed += d.amount;
        }
      }
      setDue(owe || owed ? `owe ₹${owe} · owed ₹${owed}` : 'all settled ✓');
    } catch { setDue(''); }
    try {
      const n = await notifications();
      const items = [];
      (n.alerts || []).forEach(a => items.push(`🎯 ${a.text}`));
      if ((n.captcha || 0) > 0) items.push(`🧩 ${n.captcha} captcha(s) need you — open the extension popup`);
      const p = await pendingApprovals();
      if (p.length) items.push(`⏳ ${p.length} approval(s) waiting`);
      const due = await loopsDue();
      if (due.length) items.push(`🔁 ${due.length} loop(s) due`);
      try {
        const nz = await nudges();
        nz.slice(0, 3).forEach(n => items.push(`🔔 ${n.text}`));
      } catch {}
      try {
        const u = await usageSummary();
        if (u.month_spent_usd) setSpend(`🤖 AI spend $${u.month_spent_usd} this month`);
      } catch {}
      setAlerts(items.slice(0, 6));
    } catch { setAlerts([]); }
    setRef(false);
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <Text style={s.hello}>Welcome back</Text>
      {!!spend && <Text style={s.spend}>{spend}</Text>}
      {alerts.map((a, i) => (
        <Text key={i} style={s.bell} numberOfLines={2} ellipsizeMode="tail">{a}</Text>
      ))}
      <ScrollView
        contentContainerStyle={s.grid}
        refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); load(); }} />}
      >
        {CARDS.map(c => (
          <TouchableOpacity key={c.id} style={[s.card, { backgroundColor: c.bg }]} onPress={() => router.push(c.route)}>
            <Text style={s.emoji}>{c.emoji}</Text>
            <Text style={s.title}>{c.title}</Text>
            {c.id === 'bills' && !!due && <Text style={s.sub}>{due}</Text>}
            <View style={s.go}><Text style={s.goT}>↗</Text></View>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg },
  hello: { fontSize: 20, fontWeight: '800', color: colors.text, padding: spacing.lg },
  bell: { color: colors.warning, fontSize: 13, paddingHorizontal: spacing.lg, marginBottom: 4 },
  spend: { color: colors.text, opacity: 0.7, fontSize: 12, paddingHorizontal: spacing.lg, marginBottom: 6 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', padding: spacing.md, gap: 12 },
  card: { width: '47%', borderRadius: radius.lg, padding: 16, minHeight: 150, justifyContent: 'flex-end' },
  emoji: { fontSize: 30, marginBottom: 8 },
  title: { color: '#fff', fontSize: 16, fontWeight: '800' },
  sub: { color: '#ffffffcc', fontSize: 12, marginTop: 2 },
  go: { position: 'absolute', right: 12, bottom: 12, width: 30, height: 30, borderRadius: 15, backgroundColor: '#ffffff33', alignItems: 'center', justifyContent: 'center' },
  goT: { color: '#fff', fontWeight: '700' },
});

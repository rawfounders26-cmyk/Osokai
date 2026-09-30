// Goals — watched goals with alerts (price/text/change). No new tab; linked from Settings.
import { useState, useCallback } from 'react';
import { View, Text, TextInput, StyleSheet, TouchableOpacity, ScrollView, RefreshControl, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { colors, radius, spacing } from '../services/theme';

async function g(path, opts = {}) {
  const { loadConfig } = await import('../services/config');
  const cfg = await loadConfig();
  const headers = { 'Content-Type': 'application/json' };
  if (cfg.authToken) headers['Authorization'] = `Bearer ${cfg.authToken}`;
  const base = cfg.serverUrl || 'http://127.0.0.1:8765';
  const r = await fetch(`${base}${path}`, { headers, ...opts });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export default function GoalsScreen() {
  const insets = useSafeAreaInsets();
  const [goals, setGoals] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [kind, setKind] = useState('change');
  const [ref, setRef] = useState(false);

  const load = useCallback(async () => {
    try {
      const [g1, g2] = await Promise.all([
        g('/goals').catch(() => ({ goals: [] })),
        g('/goals/alerts').catch(() => ({ alerts: [] })),
      ]);
      setGoals(g1.goals || []);
      setAlerts(g2.alerts || []);
    } catch (e) { Alert.alert('offline', `${e.message}`); }
    setRef(false);
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const create = async () => {
    if (!title.trim() || !url.trim()) { Alert.alert('Title + URL needed'); return; }
    try {
      await g('/goals', { method: 'POST', body: JSON.stringify({ title, url, kind }) });
      setTitle(''); setUrl('');
      load();
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const remove = async (id) => {
    try { await g(`/goals/${id}`, { method: 'DELETE' }); load(); }
    catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const check = async (id) => {
    try {
      const j = await g(`/goals/${id}/check`, { method: 'POST' });
      Alert.alert(j.alerts?.length ? 'Changed!' : 'No change', JSON.stringify(j.alerts || []));
      load();
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={s.page} refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); load(); }} />}>
        <Text style={s.title}>Watched goals</Text>
        {alerts.map(a => (
          <Text key={a.id} style={s.alert}>🔔 {a.text}</Text>
        ))}
        {goals.map(x => (
          <View key={x.id} style={s.row}>
            <View style={{ flex: 1 }}>
              <Text style={s.name}>{x.title}</Text>
              <Text style={s.sub}>{x.kind} · {x.url.slice(0, 44)}</Text>
            </View>
            <TouchableOpacity onPress={() => check(x.id)}><Text style={s.act}>check</Text></TouchableOpacity>
            <TouchableOpacity onPress={() => remove(x.id)}><Text style={s.del}>✕</Text></TouchableOpacity>
          </View>
        ))}
        <Text style={s.sub}>New watch</Text>
        <TextInput style={s.input} value={title} onChangeText={setTitle} placeholder="Title (iPhone price)" placeholderTextColor={colors.sub} />
        <TextInput style={s.input} value={url} onChangeText={setUrl} placeholder="https://…" placeholderTextColor={colors.sub} autoCapitalize="none" />
        <View style={s.kinds}>
          {['change', 'price', 'text'].map(k => (
            <TouchableOpacity key={k} style={[s.chip, kind === k && s.chipOn]} onPress={() => setKind(k)}>
              <Text style={s.chipT}>{k}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity style={s.btn} onPress={create}><Text style={s.btnT}>Watch</Text></TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg },
  page: { padding: spacing.lg, gap: 10 },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  alert: { color: colors.warning, fontSize: 13 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12 },
  name: { color: colors.text, fontWeight: '600' },
  sub: { color: colors.sub, fontSize: 12 },
  act: { color: colors.primary, fontWeight: '700' },
  del: { color: colors.error, fontSize: 16, paddingHorizontal: 4 },
  input: { backgroundColor: colors.surface, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 13 },
  kinds: { flexDirection: 'row', gap: 8 },
  chip: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: 7, paddingHorizontal: 13 },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipT: { color: '#fff', fontSize: 12 },
  btn: { backgroundColor: colors.primary, borderRadius: radius.md, padding: 14, alignItems: 'center' },
  btnT: { color: '#fff', fontWeight: '700' },
});

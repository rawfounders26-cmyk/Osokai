// Agent Loop — running + completed loops. Tap to close. Live-synced.
import { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, RefreshControl, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { loopsList, loopClose, onSync } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

const KIND_ICON = { reply: '💬', call: '📞', save: '🔖', promise: '✓', habit: '🔁' };

function dueStr(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  return d.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' });
}

export default function LoopsScreen() {
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState([]);
  const [done, setDone] = useState([]);
  const [ref, setRef] = useState(false);

  const load = useCallback(async (silent = false) => {
    try {
      const [o, d] = await Promise.all([loopsList('open'), loopsList('done')]);
      setOpen(o.loops || []);
      setDone((d.loops || []).slice(0, 20));
    } catch (e) { if (!silent) Alert.alert('offline', `${e.message}`); }
    setRef(false);
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useEffect(() => onSync(() => load(true)), [load]);

  const close = async (id) => {
    try { await loopClose(id); load(true); }
    catch (e) { Alert.alert('error', `${e.message}`); }
  };

  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <Text style={s.title}>Agent Loop</Text>
      <ScrollView
        contentContainerStyle={s.page}
        refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); load(); }} />}
      >
        <Text style={s.sub}>Running ({open.length}) — tap to close ✓</Text>
        {open.length === 0 && <Text style={s.empty}>no open loops — capture one from chat</Text>}
        {open.map(l => (
          <TouchableOpacity key={l.id} style={s.row} onPress={() => close(l.id)}>
            <Text style={s.ic}>{KIND_ICON[l.kind] || '○'}</Text>
            <View style={s.meta}>
              <Text style={s.t}>{l.title}</Text>
              <Text style={s.src}>{l.source}{l.due ? ` · due ${dueStr(l.due)}` : ''}</Text>
            </View>
          </TouchableOpacity>
        ))}
        <Text style={s.sub}>Completed ({done.length})</Text>
        {done.map(l => (
          <View key={l.id} style={[s.row, s.doneRow]}>
            <Text style={s.ic}>✓</Text>
            <View style={s.meta}>
              <Text style={[s.t, s.doneT]}>{l.title}</Text>
              <Text style={s.src}>{l.source}</Text>
            </View>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg },
  title: { fontSize: 22, fontWeight: '800', color: colors.text, padding: spacing.lg },
  page: { padding: spacing.lg, paddingTop: 0, gap: 10 },
  sub: { color: '#fff', fontSize: 15, fontWeight: '700', marginTop: 6 },
  empty: { color: colors.sub },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12 },
  doneRow: { opacity: 0.6 },
  ic: { fontSize: 20 },
  meta: { flex: 1 },
  t: { color: colors.text, fontSize: 15 },
  doneT: { textDecorationLine: 'line-through' },
  src: { color: colors.sub, fontSize: 12 },
});

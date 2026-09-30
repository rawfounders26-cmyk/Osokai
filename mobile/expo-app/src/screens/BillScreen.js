// Osok-AI Bill Splitter — groups, outstanding, Split Now, settle.
import { useState, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, RefreshControl, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect, router } from 'expo-router';
import { billGroups, billBalances, billSettle, billActivity } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

export default function BillScreen() {
  const insets = useSafeAreaInsets();
  const [groups, setGroups] = useState([]);
  const [gid, setGid] = useState(null);
  const [bal, setBal] = useState(null);
  const [recent, setRecent] = useState([]);
  const [ref, setRef] = useState(false);

  const load = useCallback(async () => {
    try {
      const g = await billGroups();
      setGroups(g.groups || []);
      const first = gid ?? g.groups?.[0]?.id ?? null;
      if (first) {
        setGid(first);
        setBal(await billBalances(first));
        const a = await billActivity(first);
        setRecent((a.activity || []).slice(0, 5));
      }
    } catch (e) { Alert.alert('offline', `${e.message}`); }
    setRef(false);
  }, [gid]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const g = groups.find(x => x.id === gid);
  let owe = 0, owed = 0;
  for (const grp of groups) for (const d of grp.balances || []) {
    if (d.from === 'Me') owe += d.amount;
    if (d.to === 'Me') owed += d.amount;
  }

  const settleOne = async (d) => {
    try {
      await billSettle(gid, d.from, d.to, d.amount);
      const [b, grp] = await Promise.all([billBalances(gid), billGroups()]);
      setBal(b); setGroups(grp.groups || []);
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={s.page} refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); load(); }} />}>
        <Text style={s.title}>Bill Splitter</Text>
        <View style={s.totalCard}>
          <Text style={s.totalL}>Your position</Text>
          <Text style={s.totalV}>owe ₹{owe} · owed ₹{owed}</Text>
          <TouchableOpacity style={s.splitBtn} onPress={() => gid && router.push({ pathname: '/split', params: { gid: String(gid) } })}>
            <Text style={s.splitT}>Split Now</Text>
          </TouchableOpacity>
        </View>

        <Text style={s.sub}>Groups</Text>
        {groups.map(x => (
          <TouchableOpacity key={x.id} style={[s.grow, gid === x.id && s.growOn]} onPress={() => { setGid(x.id); }}>
            <Text style={s.gname}>{x.name}</Text>
            <Text style={s.gmem}>{(x.members || []).join(', ')}</Text>
          </TouchableOpacity>
        ))}

        {bal && bal.debts?.length > 0 && (
          <>
            <Text style={s.sub}>Balances — tap to settle</Text>
            {bal.debts.map((d, i) => (
              <TouchableOpacity key={i} style={s.debt} onPress={() => settleOne(d)}>
                <Text style={s.debtT}>{d.from} → {d.to}: ₹{d.amount}</Text>
                <Text style={s.settle}>settle</Text>
              </TouchableOpacity>
            ))}
          </>
        )}

        {recent.length > 0 && (
          <>
            <Text style={s.sub}>Recently split</Text>
            {recent.map((a, i) => (
              <Text key={i} style={s.act}>
                {a.settle ? `${a.frm} settled ₹${a.amount} to ${a.to}` : `${a.title} — ₹${a.amount} by ${a.paid_by}`}
              </Text>
            ))}
          </>
        )}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#12101f' },
  page: { padding: spacing.lg, gap: 10 },
  title: { fontSize: 24, fontWeight: '800', color: '#fff' },
  totalCard: { backgroundColor: '#241f3d', borderRadius: radius.lg, padding: 16, gap: 8 },
  totalL: { color: colors.sub, fontSize: 12 },
  totalV: { color: '#fff', fontSize: 22, fontWeight: '800' },
  splitBtn: { backgroundColor: '#ff7a59', borderRadius: radius.md, padding: 13, alignItems: 'center', marginTop: 4 },
  splitT: { color: '#fff', fontWeight: '800', fontSize: 15 },
  sub: { color: '#fff', fontSize: 15, fontWeight: '700', marginTop: 8 },
  grow: { backgroundColor: '#1d1830', borderRadius: radius.md, padding: 12, borderWidth: 1, borderColor: 'transparent' },
  growOn: { borderColor: '#ff7a59' },
  gname: { color: '#fff', fontWeight: '700' },
  gmem: { color: colors.sub, fontSize: 12 },
  debt: { flexDirection: 'row', justifyContent: 'space-between', backgroundColor: '#1d1830', borderRadius: radius.md, padding: 12 },
  debtT: { color: '#fff' },
  settle: { color: '#ff7a59', fontWeight: '700' },
  act: { color: colors.sub, fontSize: 13 },
});

// Osok-AI Split Now — receipt card with per-person shares, Confirm/Cancel.
import { useState, useEffect } from 'react';
import { View, Text, TextInput, StyleSheet, TouchableOpacity, ScrollView, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useLocalSearchParams, router } from 'expo-router';
import { billGroups, billExpense } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

export default function SplitScreen() {
  const insets = useSafeAreaInsets();
  const { gid } = useLocalSearchParams();
  const [group, setGroup] = useState(null);
  const [title, setTitle] = useState('Team Dinner');
  const [total, setTotal] = useState('');
  const [shares, setShares] = useState({});
  const [paidBy, setPaidBy] = useState('Me');

  useEffect(() => {
    (async () => {
      try {
        const g = await billGroups();
        const grp = (g.groups || []).find(x => String(x.id) === String(gid)) ?? (g.groups || [])[0] ?? null;
        setGroup(grp);
        if (grp) {
          const eq = {};
          (grp.members || []).forEach(m => { eq[m] = 0; });
          setShares(eq);
          if (!grp.members?.includes('Me')) setPaidBy(grp.members?.[0] ?? 'Me');
        }
      } catch (e) { Alert.alert('offline', `${e.message}`); }
    })();
  }, [gid]);

  const members = group?.members || [];
  const sum = Object.values(shares).reduce((a, b) => a + (Number(b) || 0), 0);
  const target = Number(total) || 0;

  const splitEqual = () => {
    if (!members.length || !target) return;
    const each = Math.round((target / members.length) * 100) / 100;
    const eq = {};
    members.forEach(m => { eq[m] = each; });
    setShares(eq);
  };

  const bump = (m, d) => setShares(s => ({ ...s, [m]: Math.max(0, (Number(s[m]) || 0) + d) }));

  const confirm = async () => {
    if (!target) { Alert.alert('Enter the total bill first'); return; }
    if (Math.abs(sum - target) > 1) { Alert.alert(`Shares add to ₹${sum}, bill is ₹${target}`); return; }
    try {
      await billExpense(Number(group.id), title || 'Split', target, paidBy, shares);
      router.back();
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <Text style={s.title}>Split Now</Text>
      <ScrollView contentContainerStyle={s.page}>
        <View style={s.receipt}>
          <Text style={s.rTitle}>Receipt</Text>
          <TextInput style={s.rInput} value={title} onChangeText={setTitle} placeholder="Title" placeholderTextColor="#8a8a96" />
          <TextInput style={s.rInput} value={total} onChangeText={setTotal} placeholder="Total bill ₹" placeholderTextColor="#8a8a96" keyboardType="numeric" />
          <Text style={s.rTotal}>₹{target || '—'}</Text>
          <Text style={s.rSub}>Splitting with: {members.join(', ')}</Text>
        </View>

        <TouchableOpacity style={s.eq} onPress={splitEqual}><Text style={s.eqT}>Split equally</Text></TouchableOpacity>

        {members.map(m => (
          <View key={m} style={s.row}>
            <TouchableOpacity onPress={() => setPaidBy(m)}>
              <Text style={{ color: paidBy === m ? '#7CFC98' : colors.sub }}>{paidBy === m ? '●' : '○'} {m}</Text>
            </TouchableOpacity>
            <View style={s.step}>
              <TouchableOpacity onPress={() => bump(m, -50)}><Text style={s.stepT}>−</Text></TouchableOpacity>
              <Text style={s.amt}>₹{shares[m] || 0}</Text>
              <TouchableOpacity onPress={() => bump(m, 50)}><Text style={s.stepT}>+</Text></TouchableOpacity>
            </View>
          </View>
        ))}
        <Text style={s.sum}>shares ₹{sum} / bill ₹{target} {Math.abs(sum - target) <= 1 && target ? '✓' : ''}</Text>

        <View style={s.btns}>
          <TouchableOpacity style={[s.btn, s.ok]} onPress={confirm}><Text style={s.btnT}>Confirm Split</Text></TouchableOpacity>
          <TouchableOpacity style={[s.btn, s.no]} onPress={() => router.back()}><Text style={s.btnT}>Cancel</Text></TouchableOpacity>
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#12101f' },
  title: { fontSize: 22, fontWeight: '800', color: '#fff', padding: spacing.lg },
  page: { padding: spacing.lg, paddingTop: 0, gap: 10 },
  receipt: { backgroundColor: '#ff9d76', borderRadius: radius.lg, padding: 16, gap: 8 },
  rTitle: { color: '#5b2b1a', fontWeight: '800' },
  rInput: { backgroundColor: '#ffffff55', borderRadius: radius.md, padding: 10, color: '#3a1c10' },
  rTotal: { color: '#3a1c10', fontSize: 28, fontWeight: '800' },
  rSub: { color: '#5b2b1a', fontSize: 12 },
  eq: { backgroundColor: '#241f3d', borderRadius: radius.md, padding: 12, alignItems: 'center' },
  eqT: { color: '#fff', fontWeight: '700' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#1d1830', borderRadius: radius.md, padding: 12 },
  step: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  stepT: { color: '#ff7a59', fontSize: 22, fontWeight: '800', paddingHorizontal: 6 },
  amt: { color: '#fff', fontWeight: '700', minWidth: 70, textAlign: 'right' },
  sum: { color: colors.sub, textAlign: 'right' },
  btns: { flexDirection: 'row', gap: 10 },
  btn: { flex: 1, borderRadius: radius.md, padding: 14, alignItems: 'center' },
  ok: { backgroundColor: '#ff7a59' }, no: { backgroundColor: '#2a2438' },
  btnT: { color: '#fff', fontWeight: '800' },
});

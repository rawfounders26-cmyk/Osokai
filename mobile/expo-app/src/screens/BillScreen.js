// Osok-AI Bill Splitter — groups, outstanding, Split Now, settle.
import { useState, useCallback } from 'react';
import { View, Text, TextInput, StyleSheet, TouchableOpacity, ScrollView, RefreshControl, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect, router } from 'expo-router';
import { Linking } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { billGroups, billBalances, billSettle, billActivity, billSettleUp, billSetUpi,
  billRecurringList, billRecurringAdd, billHouseLedger, billReceipt, billExpense, billMkgroup } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

export default function BillScreen() {
  const insets = useSafeAreaInsets();
  const [groups, setGroups] = useState([]);
  const [gid, setGid] = useState(null);
  const [bal, setBal] = useState(null);
  const [recent, setRecent] = useState([]);
  const [ref, setRef] = useState(false);
  const [debts, setDebts] = useState([]);
  const [ledger, setLedger] = useState('');
  const [recs, setRecs] = useState([]);
  const [upiId, setUpiId] = useState('');
  const [grpName, setGrpName] = useState('');
  const [grpMembers, setGrpMembers] = useState('Me');
  const [recTitle, setRecTitle] = useState('');
  const [recAmt, setRecAmt] = useState('');
  const [recDay, setRecDay] = useState('1');

  const load = useCallback(async () => {
    try {
      const g = await billGroups();
      setGroups(g.groups || []);
      const first = gid ?? g.groups?.[0]?.id ?? null;
      if (first) {
        setGid(first);
        const [b, a, su, lg, rc] = await Promise.all([
          billBalances(first), billActivity(first), billSettleUp(first),
          billHouseLedger(first), billRecurringList(first),
        ]);
        setBal(b);
        setRecent((a.activity || []).slice(0, 5));
        setDebts(su.debts || []);
        setLedger(lg.reply || '');
        setRecs(rc.recurring || []);
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
      const [b, grp, su] = await Promise.all([billBalances(gid), billGroups(), billSettleUp(gid)]);
      setBal(b); setGroups(grp.groups || []); setDebts(su.debts || []);
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const payViaUpi = async (d) => {
    if (!d.upi) { Alert.alert('No UPI id', `Ask ${d.to} to set their UPI id first`); return; }
    try { await Linking.openURL(d.upi); } catch { Alert.alert('No UPI app found'); }
  };

  const saveUpi = async () => {
    if (!upiId.includes('@')) { Alert.alert('Enter a valid UPI id (name@bank)'); return; }
    try { await billSetUpi(gid, 'Me', upiId.trim()); setUpiId(''); load(); }
    catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const addRec = async () => {
    if (!recTitle.trim() || !Number(recAmt)) { Alert.alert('Title + amount needed'); return; }
    try {
      await billRecurringAdd(gid, recTitle.trim(), Number(recAmt), 'Me', Math.max(1, Math.min(28, parseInt(recDay) || 1)));
      setRecTitle(''); setRecAmt(''); load();
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const mkGroup = async () => {
    if (!grpName.trim()) { Alert.alert('Name the group first'); return; }
    try {
      const members = grpMembers.split(',').map(m => m.trim()).filter(Boolean);
      const r = await billMkgroup(grpName.trim(), members.length ? members : ['Me']);
      setGrpName(''); setGrpMembers('Me'); setGid(r.id);
      load();
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const scanReceipt = async () => {    try {
      const res = await ImagePicker.launchImageLibraryAsync({ base64: true, quality: 0.6 });
      if (res.canceled || !res.assets?.[0]?.base64) return;
      const r = await billReceipt(res.assets[0].base64);
      const d = r.draft || {};
      Alert.alert('Receipt read', `${d.title} — ₹${d.total}. Opening split…`);
      router.push({ pathname: '/split', params: { gid: String(gid), title: d.title || 'Receipt', total: String(d.total || '') } });
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
          <TouchableOpacity style={s.scanBtn} onPress={scanReceipt}>
            <Text style={s.splitT}>🧾 Scan receipt</Text>
          </TouchableOpacity>
        </View>

        <Text style={s.sub}>Groups</Text>
        {groups.map(x => (
          <TouchableOpacity key={x.id} style={[s.grow, gid === x.id && s.growOn]} onPress={() => { setGid(x.id); }}>
            <Text style={s.gname}>{x.name}</Text>
            <Text style={s.gmem}>{(x.members || []).join(', ')}</Text>
          </TouchableOpacity>
        ))}
        <View style={s.upiRow}>
          <TextInput style={[s.input, s.upiGrow]} value={grpName} onChangeText={setGrpName} placeholder="New group name" placeholderTextColor={colors.sub} />
        </View>
        <View style={s.upiRow}>
          <TextInput style={[s.input, s.upiGrow]} value={grpMembers} onChangeText={setGrpMembers} placeholder="Members, comma separated" placeholderTextColor={colors.sub} />
          <TouchableOpacity style={s.upiSave} onPress={mkGroup}><Text style={s.upiT}>Create</Text></TouchableOpacity>
        </View>

        {bal && bal.debts?.length > 0 && (
          <>
            <Text style={s.sub}>Balances — tap to settle, UPI button pays instantly</Text>
            {bal.debts.map((d, i) => {
              const su = debts.find(x => x.from === d.from && x.to === d.to) || {};
              return (
                <View key={i} style={s.debt}>
                  <TouchableOpacity style={s.debtGrow} onPress={() => settleOne(d)}>
                    <Text style={s.debtT}>{d.from} → {d.to}: ₹{d.amount}</Text>
                    <Text style={s.settle}>settle</Text>
                  </TouchableOpacity>
                  {!!su.upi && (
                    <TouchableOpacity style={s.upiBtn} onPress={() => payViaUpi(su)}>
                      <Text style={s.upiT}>UPI ⬆</Text>
                    </TouchableOpacity>
                  )}
                </View>
              );
            })}
            <View style={s.upiRow}>
              <TextInput style={[s.input, s.upiGrow]} value={upiId} onChangeText={setUpiId} placeholder="My UPI id (me@okhdfc)" placeholderTextColor={colors.sub} autoCapitalize="none" />
              <TouchableOpacity style={s.upiSave} onPress={saveUpi}><Text style={s.upiT}>Save</Text></TouchableOpacity>
            </View>
          </>
        )}

        {!!ledger && (
          <>
            <Text style={s.sub}>House ledger</Text>
            <Text style={s.ledger}>{ledger}</Text>
          </>
        )}

        <Text style={s.sub}>Monthly repeats</Text>
        {recs.map(r => (
          <Text key={r.id} style={s.act}>🔁 {r.title} ₹{r.amount} · day {r.day} · by {r.paid_by}</Text>
        ))}
        <TextInput style={s.input} value={recTitle} onChangeText={setRecTitle} placeholder="Repeat title (rent)" placeholderTextColor={colors.sub} />
        <View style={s.upiRow}>
          <TextInput style={[s.input, s.upiGrow]} value={recAmt} onChangeText={setRecAmt} placeholder="₹ amount" placeholderTextColor={colors.sub} keyboardType="numeric" />
          <TextInput style={[s.input, s.upiGrow]} value={recDay} onChangeText={setRecDay} placeholder="day 1-28" placeholderTextColor={colors.sub} keyboardType="numeric" />
          <TouchableOpacity style={s.upiSave} onPress={addRec}><Text style={s.upiT}>Repeat</Text></TouchableOpacity>
        </View>

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
  scanBtn: { backgroundColor: '#2a2438', borderRadius: radius.md, padding: 13, alignItems: 'center', marginTop: 8, borderWidth: 1, borderColor: '#ff7a59' },
  debtGrow: { flex: 1, flexDirection: 'row', justifyContent: 'space-between' },
  upiBtn: { backgroundColor: '#7CFC98', borderRadius: radius.md, paddingVertical: 6, paddingHorizontal: 12, marginLeft: 8 },
  upiT: { color: '#0b2e13', fontWeight: '800' },
  upiRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  upiGrow: { flex: 1 },
  upiSave: { backgroundColor: '#241f3d', borderRadius: radius.md, paddingVertical: 12, paddingHorizontal: 16, justifyContent: 'center', borderWidth: 1, borderColor: '#7CFC98' },
  input: { backgroundColor: '#241f3d', color: '#fff', borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12, marginTop: 8 },
  ledger: { color: colors.sub, fontSize: 13, backgroundColor: '#1d1830', borderRadius: radius.md, padding: 12 },
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

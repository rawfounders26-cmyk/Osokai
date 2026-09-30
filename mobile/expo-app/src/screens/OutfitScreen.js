// Outfit Planner — today's suggestion + wardrobe + feedback. Same screen, no new nav.
import { useState, useCallback } from 'react';
import { View, Text, TextInput, StyleSheet, TouchableOpacity, ScrollView, RefreshControl, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { wardrobeItems, wardrobeAdd, wardrobeSuggest, wardrobeFeedback, wardrobeWorn, wardrobePrefs } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

export default function OutfitScreen() {
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState([]);
  const [sug, setSug] = useState(null);
  const [prefs, setPrefs] = useState([]);
  const [form, setForm] = useState({ category: '', color: '', season: 'all', formality: 'casual' });
  const [occ, setOcc] = useState('');
  const [ref, setRef] = useState(false);

  const load = useCallback(async () => {
    try {
      const [it, s, p] = await Promise.all([wardrobeItems(), wardrobeSuggest(), wardrobePrefs()]);
      setItems(it.items || []); setSug(s); setPrefs(p.prefs || []);
    } catch (e) { Alert.alert('offline', `${e.message}`); }
    setRef(false);
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const suggestFor = async () => {
    try { setSug(await wardrobeSuggest(occ)); } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const add = async () => {
    if (!form.category.trim()) { Alert.alert('Name the item first (e.g. linen shirt)'); return; }
    try {
      await wardrobeAdd(form);
      setForm({ category: '', color: '', season: 'all', formality: 'casual' });
      load();
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const fb = async (id, good) => {
    try { await wardrobeFeedback(id, good); load(); } catch (e) { Alert.alert('error', `${e.message}`); }
  };

  const w = sug?.weather || {};
  const cands = (sug?.candidates || []).slice(0, 3);

  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={s.page} refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); load(); }} />}>
        <Text style={s.title}>Outfit Planner</Text>

        <View style={s.card}>
          <Text style={s.cardT}>Today · {w.temp != null ? `${w.temp}°C` : '…'} {w.humidity != null ? `· ${w.humidity}% humidity` : ''}</Text>
          <TextInput style={s.input} value={occ} onChangeText={setOcc} placeholder="Occasion (office, gym…) — empty = any" placeholderTextColor={colors.sub} />
          <TouchableOpacity style={s.btn} onPress={suggestFor}><Text style={s.btnT}>Suggest for occasion</Text></TouchableOpacity>
          {cands.map(c => (
            <View key={c.id} style={s.pick}>
              <Text style={s.pickT}>{c.color} {c.category} <Text style={s.pickS}>({c.season}, {c.formality})</Text></Text>
              <View style={s.pickBtns}>
                <TouchableOpacity onPress={() => fb(c.id, true)}><Text style={s.up}>👍</Text></TouchableOpacity>
                <TouchableOpacity onPress={() => fb(c.id, false)}><Text style={s.up}>👎</Text></TouchableOpacity>
                <TouchableOpacity onPress={async () => { await wardrobeWorn(c.id); load(); }}><Text style={s.wore}>wore it</Text></TouchableOpacity>
              </View>
            </View>
          ))}
          {(sug?.prefs || []).slice(0, 3).map((p, i) => <Text key={i} style={s.pref}>· remembers: {p}</Text>)}
        </View>

        <Text style={s.sub}>Wardrobe ({items.length})</Text>
        {items.map(it => (
          <View key={it.id} style={s.row}>
            <Text style={s.rowT}>{it.color} {it.category}</Text>
            <Text style={s.rowS}>{it.season} · {it.formality} · worn {it.wears}x</Text>
          </View>
        ))}

        <Text style={s.sub}>Add item</Text>
        <TextInput style={s.input} value={form.category} onChangeText={v => setForm({ ...form, category: v })} placeholder="Category (linen shirt)" placeholderTextColor={colors.sub} />
        <TextInput style={s.input} value={form.color} onChangeText={v => setForm({ ...form, color: v })} placeholder="Color (blue)" placeholderTextColor={colors.sub} />
        <View style={s.chips}>
          {['all', 'summer', 'winter', 'monsoon'].map(x => (
            <TouchableOpacity key={x} style={[s.chip, form.season === x && s.chipOn]} onPress={() => setForm({ ...form, season: x })}>
              <Text style={s.chipT}>{x}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <View style={s.chips}>
          {['casual', 'smart-casual', 'formal', 'activewear'].map(x => (
            <TouchableOpacity key={x} style={[s.chip, form.formality === x && s.chipOn]} onPress={() => setForm({ ...form, formality: x })}>
              <Text style={s.chipT}>{x}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <TouchableOpacity style={s.btn} onPress={add}><Text style={s.btnT}>Add to wardrobe</Text></TouchableOpacity>
        {prefs.length > 0 && <Text style={s.sub}>Style memory</Text>}
        {prefs.map((p, i) => <Text key={i} style={s.pref}>· {p}</Text>)}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg },
  page: { padding: spacing.lg, gap: 10 },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  card: { backgroundColor: '#241f3d', borderRadius: radius.lg, padding: 14, gap: 8 },
  cardT: { color: '#fff', fontWeight: '700' },
  sub: { color: '#fff', fontSize: 15, fontWeight: '700', marginTop: 8 },
  input: { backgroundColor: colors.surface, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12 },
  btn: { backgroundColor: '#8e4ec6', borderRadius: radius.md, padding: 13, alignItems: 'center' },
  btnT: { color: '#fff', fontWeight: '800' },
  pick: { backgroundColor: '#1d1830', borderRadius: radius.md, padding: 12, gap: 6 },
  pickT: { color: '#fff', fontWeight: '700' },
  pickS: { color: colors.sub, fontWeight: '400' },
  pickBtns: { flexDirection: 'row', gap: 14, alignItems: 'center' },
  up: { fontSize: 18 },
  wore: { color: '#7CFC98' },
  pref: { color: colors.sub, fontSize: 12 },
  row: { backgroundColor: colors.surface, borderRadius: radius.md, padding: 12, borderWidth: 1, borderColor: colors.border },
  rowT: { color: colors.text, fontWeight: '600' },
  rowS: { color: colors.sub, fontSize: 12 },
  chips: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  chip: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: 7, paddingHorizontal: 13 },
  chipOn: { backgroundColor: '#8e4ec6', borderColor: '#8e4ec6' },
  chipT: { color: '#fff', fontSize: 12 },
});

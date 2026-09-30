// Osok-AI Files — same VM store the agent saves to. Folders navigate, back goes up.
import { useState, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, RefreshControl, Alert, TouchableOpacity } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { getFiles } from '../services/api';
import { colors, spacing } from '../services/theme';

export default function FilesScreen() {
  const insets = useSafeAreaInsets();
  const [entries, setEntries] = useState([]);
  const [path, setPath] = useState('');
  const [ref, setRef] = useState(false);
  const load = useCallback(async (p) => {
    try {
      const j = await getFiles(p);
      setEntries(j.entries || (j.workspace || []).map(n => ({ name: n, dir: false })));
      setPath(j.path || p || '');
    } catch (e) { Alert.alert('offline', `${e.message}`); }
    setRef(false);
  }, []);
  useFocusEffect(useCallback(() => { load(''); }, [load]));
  const up = () => {
    if (!path) return;
    const parts = path.split('/').filter(Boolean);
    parts.pop();
    load(parts.join('/'));
  };
  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <Text style={s.title}>Files {path ? `· /${path}` : ''}</Text>
      {path ? (
        <TouchableOpacity onPress={up}><Text style={s.up}>‹ Back</Text></TouchableOpacity>
      ) : null}
      <FlatList data={entries} keyExtractor={(_, i) => `${i}`}
        refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); load(path); }} />}
        ListEmptyComponent={<Text style={s.sub}>empty — ask Osok-AI to create folders/files</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity
            disabled={!item.dir}
            onPress={() => load(path ? `${path}/${item.name}` : item.name)}
          >
            <Text style={s.row}>{item.dir ? '📁' : '📄'} {item.name}</Text>
          </TouchableOpacity>
        )} />
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, padding: spacing.lg },
  title: { fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 8 },
  up: { color: colors.primary, fontSize: 15, marginBottom: 6 },
  row: { color: colors.text, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  sub: { color: colors.sub },
});

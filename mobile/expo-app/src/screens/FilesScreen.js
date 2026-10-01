// Osok-AI Files + Goals — top toggle. Goals: Goal → Objectives → Projects → Tasks.
import { useState, useCallback } from 'react';
import { View, Text, TextInput, StyleSheet, FlatList, RefreshControl, Alert, TouchableOpacity, ScrollView } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { getFiles, readFile } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

async function gapi(path, opts = {}) {
  const { loadConfig } = await import('../services/config');
  const cfg = await loadConfig();
  const headers = { 'Content-Type': 'application/json' };
  if (cfg.authToken) headers['Authorization'] = `Bearer ${cfg.authToken}`;
  const base = cfg.serverUrl || 'http://127.0.0.1:8765';
  const r = await fetch(`${base}${path}`, { headers, ...opts });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

const ST = { todo: '○', doing: '◐', done: '●', waiting: '⏳', failed: '✕' };
const KIND = { research: '🔍', create: '🛠', browse: '🌐', approval: '💳', human: '🙋', wait: '⏳' };

function GoalTree({ g, onRun }) {
  const [open, setOpen] = useState({});
  const tog = (k) => setOpen(p => ({ ...p, [k]: !p[k] }));
  return (
    <View style={t.card}>
      <Text style={t.gtitle}>{g.title} — {g.progress}%</Text>
      {g.objectives.map(o => (
        <View key={o.id}>
          <TouchableOpacity onPress={() => tog('o' + o.id)}>
            <Text style={t.otitle}>{open['o' + o.id] ? '▾' : '▸'} {o.title} ({o.done}/{o.total})</Text>
          </TouchableOpacity>
          {open['o' + o.id] && o.projects.map(p => (
            <View key={p.id} style={t.proj}>
              <TouchableOpacity onPress={() => tog('p' + p.id)}>
                <Text style={t.ptitle}>{open['p' + p.id] ? '▾' : '▸'} {p.title}</Text>
              </TouchableOpacity>
              {open['p' + p.id] && p.tasks.map(x => (
                <View key={x.id} style={t.task}>
                  <Text style={t.taskT}>{ST[x.status] || '○'} {KIND[x.kind] || ''} {x.title}</Text>
                  {(x.status === 'todo' || x.status === 'failed') && (
                    <TouchableOpacity style={t.run} onPress={() => onRun(x.id)}>
                      <Text style={t.runT}>Run</Text>
                    </TouchableOpacity>
                  )}
                  {!!x.result && <Text style={t.res}>{x.result.slice(0, 220)}</Text>}
                </View>
              ))}
            </View>
          ))}
        </View>
      ))}
    </View>
  );
}

export default function FilesScreen() {
  const insets = useSafeAreaInsets();
  const [tab, setTab] = useState('files');
  const [entries, setEntries] = useState([]);
  const [path, setPath] = useState('');
  const [goals, setGoals] = useState([]);
  const [openGid, setOpenGid] = useState(null);
  const [tree, setTree] = useState(null);
  const [ref, setRef] = useState(false);
  const [preview, setPreview] = useState(null);

  const loadFiles = useCallback(async (p) => {
    try {
      const j = await getFiles(p);
      setEntries(j.entries || (j.workspace || []).map(n => ({ name: n, dir: false })));
      setPath(j.path || p || '');
    } catch (e) { Alert.alert('offline', `${e.message}`); }
    setRef(false);
  }, []);
  const loadGoals = useCallback(async () => {
    try {
      const j = await gapi('/goaltrees');
      setGoals(j.goals || []);
    } catch (e) { Alert.alert('offline', `${e.message}`); }
    setRef(false);
  }, []);
  useFocusEffect(useCallback(() => { loadFiles(''); loadGoals(); }, [loadFiles, loadGoals]));

  const openGoal = async (gid) => {
    if (openGid === gid) { setOpenGid(null); return; }
    setOpenGid(gid);
    try { setTree(await gapi(`/goaltrees/${gid}`)); } catch (e) { Alert.alert('error', `${e.message}`); }
  };
  const running = goals.filter(g => (g.progress ?? 0) < 100);
  const completed = goals.filter(g => (g.progress ?? 0) >= 100 && (g.total ?? 0) > 0);
  const goalBlock = (g) => (
    <View key={g.id}>
      <TouchableOpacity style={s.grow} onPress={() => openGoal(g.id)}>
        <Text style={s.gtitle}>{openGid === g.id ? '▾' : '▸'} {g.title}</Text>
        <Text style={s.gsrc}>{g.done ?? 0}/{g.total ?? 0} tasks · {g.progress ?? 0}%</Text>
      </TouchableOpacity>
      {openGid === g.id && tree && tree.id === g.id && (
        <GoalTree g={tree} onRun={runTask} />
      )}
    </View>
  );
  const runTask = async (tid) => {
    try {
      Alert.alert('Running', 'task started — pull to refresh for status');
      await gapi(`/goaltrees/tasks/${tid}/run`, { method: 'POST', body: JSON.stringify({}) });
      const t = await gapi(`/goaltrees/${openGid}`);
      setTree(t);
    } catch (e) { Alert.alert('error', `${e.message}`); }
  };
  const up = () => {
    if (!path) return;
    const parts = path.split('/').filter(Boolean);
    parts.pop();
    loadFiles(parts.join('/'));
  };

  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <View style={s.tabs}>
        {['files', 'goals'].map(k => (
          <TouchableOpacity key={k} style={[s.tab, tab === k && s.tabOn]} onPress={() => setTab(k)}>
            <Text style={[s.tabT, tab === k && s.tabTOn]}>{k === 'files' ? 'Files' : 'Goals'}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {tab === 'files' ? (
        <>
          <Text style={s.title}>Files {path ? `· /${path}` : ''}</Text>
          {path ? (
            <TouchableOpacity onPress={up}><Text style={s.up}>‹ Back</Text></TouchableOpacity>
          ) : null}
          <FlatList data={entries} keyExtractor={(_, i) => `${i}`}
            refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); loadFiles(path); }} />}
            ListEmptyComponent={<Text style={s.sub}>empty — ask Osok-AI to create folders/files</Text>}
            renderItem={({ item }) => {
              const full = path ? `${path}/${item.name}` : item.name;
              const isOpen = preview && preview.path === full;
              return (
                <View>
                  <TouchableOpacity
                    onPress={() => {
                      if (item.dir) { setPreview(null); loadFiles(full); }
                      else if (isOpen) setPreview(null);
                      else readFile(full).then(j => setPreview({ path: full, content: j.content || '' })).catch(e => Alert.alert('error', `${e.message}`));
                    }}
                  >
                    <Text style={s.row}>{item.dir ? '📁' : '📄'} {item.name}</Text>
                  </TouchableOpacity>
                  {isOpen && <Text style={s.preview}>{preview.content.slice(0, 3000)}</Text>}
                </View>
              );
            }} />
        </>
      ) : (
        <ScrollView
          contentContainerStyle={{ gap: 10, paddingBottom: 20 }}
          refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); loadGoals(); }} />}
        >
          <Text style={s.sect}>Running ({running.length}) — give goals from chat</Text>
          {running.map(goalBlock)}
          {running.length === 0 && <Text style={s.sub}>nothing running — tell chat a goal</Text>}
          <Text style={s.sect}>Completed ({completed.length})</Text>
          {completed.map(goalBlock)}
          {completed.length === 0 && <Text style={s.sub}>nothing completed yet</Text>}
        </ScrollView>
      )}
    </View>
  );
}

const t = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12, gap: 8 },
  gtitle: { color: colors.text, fontSize: 16, fontWeight: '800' },
  otitle: { color: colors.text, fontSize: 14, fontWeight: '700', marginTop: 6 },
  proj: { marginLeft: 10, gap: 4 },
  ptitle: { color: colors.text, fontSize: 13, fontWeight: '600' },
  task: { marginLeft: 10, backgroundColor: colors.bg, borderRadius: radius.sm, padding: 8, gap: 4 },
  taskT: { color: colors.text, fontSize: 13 },
  res: { color: colors.sub, fontSize: 11 },
  run: { backgroundColor: colors.primary, borderRadius: radius.sm, paddingVertical: 6, alignItems: 'center' },
  runT: { color: '#fff', fontWeight: '700', fontSize: 12 },
});

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, padding: spacing.lg },
  tabs: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  tab: { flex: 1, padding: 10, borderRadius: radius.md, backgroundColor: colors.surface, alignItems: 'center', borderWidth: 1, borderColor: colors.border },
  tabOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  tabT: { color: colors.sub, fontWeight: '700' },
  tabTOn: { color: '#fff' },
  title: { fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 8 },
  up: { color: colors.primary, fontSize: 15, marginBottom: 6 },
  row: { color: colors.text, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  preview: { color: colors.sub, fontSize: 12, backgroundColor: colors.surface, borderRadius: radius.sm, padding: 10, marginBottom: 8 },
  sub: { color: colors.sub },
  sect: { color: '#fff', fontSize: 15, fontWeight: '800', marginTop: 6 },
  input: { backgroundColor: colors.surface, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12 },
  btnrow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  btn: { backgroundColor: colors.primary, borderRadius: radius.md, padding: 12, alignItems: 'center', flex: 1 },
  btn2: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12, alignItems: 'center', flex: 1 },
  btnT: { color: '#fff', fontWeight: '700' },
  grow: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12 },
  gtitle: { color: colors.text, fontWeight: '700' },
  gsrc: { color: colors.sub, fontSize: 11 },
});

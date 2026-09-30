// Osok-AI Chat — AI Assistant look, approvals inline.
import { useState, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator, Linking,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { SvgXml } from 'react-native-svg';
import { useAudioRecorder, useAudioRecorderState, RecordingPresets, requestRecordingPermissionsAsync } from 'expo-audio';
import { chat, listPendingApprovals, decideApproval, loopSnooze, voiceTranscribe } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

const OSOKAI_BLOB = `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="p" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#a855f7"/><stop offset="1" stop-color="#5b5bd6"/></linearGradient></defs><path d="p" fill="url(#p)"/><circle cx="38" cy="42" r="6" fill="#fff" opacity=".9"/><circle cx="62" cy="42" r="6" fill="#fff" opacity=".9"/><circle cx="39.5" cy="43.5" r="2.8" fill="#2a1b4e"/><circle cx="63.5" cy="43.5" r="2.8" fill="#2a1b4e"/><path d="M 38,62 Q 50,70 62,62" stroke="#fff" stroke-width="3.5" fill="none" stroke-linecap="round"/></svg>`;

export default function ChatScreen() {
  const insets = useSafeAreaInsets();
  const [input, setInput] = useState('');
  const [msgs, setMsgs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState([]);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recState = useAudioRecorderState(recorder);
  const recording = recState?.isRecording ?? false;
  const listRef = useRef(null);

  const refreshApprovals = async () => {
    try { setPending(await listPendingApprovals()); } catch {}
  };

  const micToggle = async () => {
    try {
      if (recording) {
        await recorder.stop();
        const uri = recorder.uri;
        if (uri) {
          const t = await voiceTranscribe(uri);
          if (t) setInput(prev => (prev ? prev + ' ' : '') + t);
        }
        return;
      }
      const perm = await requestRecordingPermissionsAsync();
      if (!perm.granted) return;
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch {}
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput(''); setBusy(true);
    const id = Date.now();
    setMsgs(p => [...p, { id: `u${id}`, role: 'user', text }, { id: `a${id}`, role: 'agent', text: '' }]);
    try {
      const j = await chat(text);
      // mobile routing: YouTube opens directly in the phone app; complex goals run on the shared VM
      if (j.action === 'youtube_play' && j.url) {
        try { await Linking.openURL(j.url); } catch {}
      }
      setMsgs(p => [...p.slice(0, -1), { id: `a${id}`, role: 'agent', text: j.reply, approval: j.approval_required ? j.approval_id : null, link: (j.action === 'open_url' || j.action === 'shop_browse') ? j.url : null }]);
      refreshApprovals();
    } catch (e) {
      setMsgs(p => [...p.slice(0, -1), { id: `a${id}`, role: 'agent', text: `${e.message}` }]);
    }
    setBusy(false);
  };

  const decide = async (id, allow) => {
    try {
      await decideApproval(id, allow);
      setMsgs(p => p.map(m => m.approval === id ? { ...m, approval: null, text: `${m.text}\n${allow ? 'Approved ✓' : 'Rejected'}` } : m));
      refreshApprovals();
    } catch (e) {}
  };

  const later = async (id) => {
    try {
      await loopSnooze(id, 3);
      setMsgs(p => p.map(m => m.approval === id ? { ...m, approval: null, text: `${m.text}\nSnoozed → loop (3h)` } : m));
      refreshApprovals();
    } catch (e) {}
  };

  const renderItem = ({ item }) => {
    if (item.role === 'user')
      return <View style={s.userRow}><Text style={s.userText}>{item.text}</Text></View>;
    return (
      <View style={s.agentRow}>
        <SvgXml xml={OSOKAI_BLOB} width={30} height={30} />
        <View style={s.agentContent}>
          {!item.text ? <ActivityIndicator size="small" color={colors.primary} /> : (
            <View style={s.answerBubble}><Text style={s.answerText} selectable>{item.text}</Text></View>
          )}
          {item.link && (
            <TouchableOpacity style={s.linkBtn} onPress={() => Linking.openURL(item.link)}>
              <Text style={s.linkT}>Open in browser ↗</Text>
            </TouchableOpacity>
          )}
          {item.approval && (
            <View style={s.appr}>
              <Text style={s.apprT}>Approval #{item.approval} — approve?</Text>
              <View style={s.apprBtns}>
                <TouchableOpacity style={[s.btn, s.ok]} onPress={() => decide(item.approval, true)}><Text style={s.okT}>Approve</Text></TouchableOpacity>
                <TouchableOpacity style={[s.btn, s.no]} onPress={() => decide(item.approval, false)}><Text style={s.noT}>Reject</Text></TouchableOpacity>
              </View>
              <TouchableOpacity onPress={() => later(item.approval)}><Text style={s.laterT}>Later → remind me in 3h</Text></TouchableOpacity>
            </View>
          )}
        </View>
      </View>
    );
  };

  return (
    <View style={[s.container, { paddingTop: insets.top }]}>
      <View style={s.header}>
        <View style={s.headerLeft}><View style={s.dot} /><Text style={s.headerTitle}>AI Assistant</Text></View>
      </View>
      {pending.length > 0 && (
        <View style={s.pendBar}><Text style={s.pendT}>{pending.length} pending approval{pending.length > 1 ? 's' : ''}</Text></View>
      )}
      <FlatList
        ref={listRef} data={msgs} renderItem={renderItem} keyExtractor={i => i.id}
        contentContainerStyle={s.list} showsVerticalScrollIndicator={false}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={
          <View style={s.empty}><Text style={s.emptyIcon}>✦</Text><Text style={s.emptyTitle}>How can I help?</Text>
          <Text style={s.emptySub}>Give me a goal — I can open apps, browse, play media and more.</Text></View>
        }
      />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={[s.inputBar, { paddingBottom: insets.bottom > 0 ? insets.bottom : 12 }]}>
          <TextInput style={s.input} value={input} onChangeText={setInput} placeholder="Message AI Assistant…"
            placeholderTextColor={colors.sub} multiline maxLength={1000} />
          <TouchableOpacity style={[s.send, recording && s.recOn]} onPress={micToggle}>
            <Text style={s.sendI}>{recording ? '■' : '🎙'}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.send, (busy || !input.trim()) && s.sendOff]} onPress={send} disabled={busy || !input.trim()}>
            {busy ? <ActivityIndicator size="small" color="#fff" /> : <Text style={s.sendI}>↑</Text>}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: spacing.lg, paddingVertical: 14, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.success },
  headerTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  pendBar: { backgroundColor: colors.warning + '22', padding: 8, alignItems: 'center' },
  pendT: { color: colors.warning, fontSize: 12, fontWeight: '700' },
  list: { padding: spacing.md, gap: 16 },
  userRow: { alignSelf: 'flex-end', backgroundColor: colors.primary, borderRadius: 20, borderBottomRightRadius: 5, paddingHorizontal: 16, paddingVertical: 11, maxWidth: '80%' },
  userText: { color: '#fff', fontSize: 15, lineHeight: 22 },
  agentRow: { flexDirection: 'row', gap: 10 },
  avatar: { width: 30, height: 30, borderRadius: 15, backgroundColor: colors.primary + '28', borderWidth: 1, borderColor: colors.primary + '50', alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  avatarTxt: { fontSize: 10, fontWeight: '800', color: colors.primary },
  agentContent: { flex: 1, gap: 6 },
  answerBubble: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 16, borderTopLeftRadius: 4, paddingHorizontal: 16, paddingVertical: 12 },
  answerText: { fontSize: 15, color: colors.text, lineHeight: 23 },
  linkBtn: { backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 10, alignItems: 'center' },
  linkT: { color: colors.primary, fontWeight: '700' },
  appr: { borderWidth: 1.5, borderColor: colors.warning + '60', borderRadius: radius.md, backgroundColor: 'rgba(245,158,11,0.06)', padding: 12, gap: 8 },
  apprT: { color: colors.warning, fontWeight: '700' },
  apprBtns: { flexDirection: 'row', gap: 8 },
  btn: { flex: 1, paddingVertical: 10, borderRadius: radius.md, alignItems: 'center' },
  ok: { backgroundColor: colors.success }, no: { backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.border },
  okT: { color: '#fff', fontWeight: '700' }, noT: { color: colors.sub, fontWeight: '600' },
  laterT: { color: colors.primary, fontSize: 12, marginTop: 4 },
  empty: { flex: 1, alignItems: 'center', paddingTop: 100, gap: 12 },
  emptyIcon: { fontSize: 36, color: colors.primary },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: colors.text },
  emptySub: { fontSize: 14, color: colors.sub, textAlign: 'center', lineHeight: 21 },
  inputBar: { flexDirection: 'row', alignItems: 'flex-end', gap: 10, paddingHorizontal: spacing.md, paddingTop: 10, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
  input: { flex: 1, backgroundColor: colors.surface2, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: 22, paddingHorizontal: 16, paddingVertical: 11, fontSize: 15, maxHeight: 120 },
  send: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  sendOff: { backgroundColor: colors.border },
  recOn: { backgroundColor: colors.error },
  sendI: { color: '#fff', fontSize: 20, fontWeight: '700' },
});

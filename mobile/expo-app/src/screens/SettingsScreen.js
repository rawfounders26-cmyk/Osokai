// Osok-AI Settings — sync (URL + token + device) + per-service connectors.
import { useState, useCallback } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, RefreshControl, Alert } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect, router } from 'expo-router';
import { loadConfig, saveConfig } from '../services/config';
import { authCheck, getConnectors, startSync, vaultStatus, vaultLock, vaultUnlock, vaultAudit, vaultList, vaultPolicy } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
  const [base, setBase] = useState('');
  const [token, setToken] = useState('');
  const [device, setDevice] = useState('');
  const [live, setLive] = useState('');
  const [conns, setConns] = useState([]);
  const [ref, setRef] = useState(false);
  const [lock, setLock] = useState(null);
  const [secrets, setSecrets] = useState([]);
  const [audit, setAudit] = useState([]);

  const load = useCallback(async () => {
    const cfg = await loadConfig();
    setBase(cfg.serverUrl); setToken(cfg.authToken); setDevice(cfg.device);
    try {
      const j = await getConnectors();
      setConns(j.connectors || []);
    } catch {}
    try { setLock(await vaultStatus()); } catch {}
    try {
      const v = await vaultList();
      setSecrets(v.secrets || []);
      const a = await vaultAudit(15);
      setAudit(a.audit || []);
    } catch {}
    setRef(false);
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const connectAll = async () => {
    await saveConfig({ serverUrl: base, authToken: token, device });
    try {
      await authCheck();
      setLive('live + synced ✓');
      load();
      startSync();
    } catch (e) { setLive(`${e.message}`); }
  };

  const connected = conns.filter(c => c.connected).length;
  return (
    <View style={[s.wrap, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={s.page} refreshControl={<RefreshControl refreshing={ref} onRefresh={() => { setRef(true); load(); }} />}>
        <Text style={s.title}>Settings — sync</Text>
        <TextInput style={s.input} value={base} onChangeText={setBase} placeholder="Backend URL" placeholderTextColor={colors.sub} autoCapitalize="none" />
        <TextInput style={s.input} value={token} onChangeText={setToken} placeholder="Osok-AI auth token" placeholderTextColor={colors.sub} secureTextEntry autoCapitalize="none" />
        <TextInput style={s.input} value={device} onChangeText={setDevice} placeholder="Device ID (mobile-app)" placeholderTextColor={colors.sub} autoCapitalize="none" />
        <TouchableOpacity style={s.btn} onPress={connectAll}><Text style={s.btnT}>Save & reconnect</Text></TouchableOpacity>
        {live ? <Text style={[s.live, { color: live.includes('✓') ? colors.success : colors.error }]}>{live}</Text> : null}
        <TouchableOpacity style={s.connCard} onPress={() => router.push('/connectors')}>
          <View>
            <Text style={s.connT}>Connectors</Text>
            <Text style={s.connS}>{conns.length ? `${connected}/${conns.length} connected` : 'WhatsApp · Gmail · Outlook · Discord · Slack'}</Text>
          </View>
          <Text style={s.connGo}>›</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.connCard} onPress={async () => {
          try {
            if (lock && !lock.locked) await vaultLock();
            else await vaultUnlock(15);
            load();
          } catch (e) { Alert.alert('vault', `${e.message}`); }
        }}>
          <View>
            <Text style={s.connT}>Vault {lock ? (lock.locked ? '🔒 locked' : `unlocked (${lock.seconds_left}s)`) : ''}</Text>
            <Text style={s.connS}>tap to lock / unlock for 15 min</Text>
          </View>
          <Text style={s.connGo}>›</Text>
        </TouchableOpacity>
        <Text style={s.sub}>Secrets — tap policy to cycle</Text>
        {secrets.map(sec => (
          <TouchableOpacity key={sec.key} style={s.secRow} onPress={async () => {
            const order = ['while-unlocked', 'always', 'never'];
            const next = order[(order.indexOf(sec.policy) + 1) % order.length] || 'while-unlocked';
            try { await vaultPolicy(sec.key, next); load(); } catch (e) { Alert.alert('vault', `${e.message}`); }
          }}>
            <View style={{ flex: 1 }}>
              <Text style={s.secK}>{sec.key} <Text style={s.secM}>{sec.masked}</Text></Text>
              <Text style={s.secS}>{(sec.domains || []).join(', ') || 'any domain'}</Text>
            </View>
            <Text style={s.secP}>{sec.policy}</Text>
          </TouchableOpacity>
        ))}
        <Text style={s.sub}>Access log</Text>
        {audit.length === 0 && <Text style={s.secS}>no accesses yet</Text>}
        {audit.map((a, i) => (
          <Text key={i} style={s.secS}>{a.allowed ? '✓' : '✕'} {a.key} · {a.domain || '-'} · {a.device} · {a.reason}</Text>
        ))}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg },
  page: { padding: spacing.lg, gap: 10 },
  title: { fontSize: 20, fontWeight: '800', color: colors.text },
  input: { backgroundColor: colors.surface, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 13 },
  btn: { backgroundColor: colors.primary, borderRadius: radius.md, padding: 14, alignItems: 'center' },
  btnT: { color: '#fff', fontWeight: '700' },
  live: { fontSize: 13 },
  connCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 14 },
  connT: { fontSize: 16, fontWeight: '700', color: colors.text },
  connS: { fontSize: 12, color: colors.sub, marginTop: 2 },
  connGo: { fontSize: 22, color: colors.sub },
  sub: { fontSize: 16, fontWeight: '700', color: colors.text, marginTop: 8 },
  secRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12 },
  secK: { color: colors.text, fontWeight: '600', flex: 1 },
  secM: { color: colors.sub, fontWeight: '400' },
  secS: { color: colors.sub, fontSize: 12 },
  secP: { color: colors.primary, fontSize: 12, fontWeight: '700' },
});

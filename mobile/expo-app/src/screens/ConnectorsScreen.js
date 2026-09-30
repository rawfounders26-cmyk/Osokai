// Osok-AI Connectors — osokai pattern: brand rows, honest status, unread badges, enable switches.
import { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, Switch, StyleSheet, TouchableOpacity,
  ScrollView, Alert, ActivityIndicator, RefreshControl,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { getConnectors, setConnectorEnabled, connectService, onSync } from '../services/api';
import { colors, radius, spacing } from '../services/theme';

const BRAND_ICON = {
  whatsapp: 'logo-whatsapp',
  slack: 'logo-slack',
  gmail: 'logo-google',
  outlook: 'logo-microsoft',
  discord: 'logo-discord',
};

export default function ConnectorsScreen() {
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(null);
  const [svcToken, setSvcToken] = useState('');
  const [showToken, setShowToken] = useState(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await getConnectors();
      setItems(res.connectors ?? []);
    } catch (e) {
      if (!silent) Alert.alert('Unreachable', `${e.message}`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => onSync(() => load(true)), [load]);

  const toggle = useCallback(async (id, enabled) => {
    setItems(prev => prev.map(c => (c.id === id ? { ...c, enabled } : c)));
    setBusy(id);
    try {
      const updated = await setConnectorEnabled(id, enabled);
      setItems(prev => prev.map(c => (c.id === id ? { ...c, ...updated } : c)));
    } catch {
      setItems(prev => prev.map(c => (c.id === id ? { ...c, enabled: !enabled } : c)));
      Alert.alert('Failed', `Could not update ${id}. Is the server reachable?`);
    } finally {
      setBusy(null);
    }
  }, []);

  const pair = async (id) => {
    if (!svcToken.trim()) { Alert.alert('Paste a service token below first, then tap Pair'); return; }
    setBusy(id);
    try {
      await connectService(id, svcToken.trim());
      setSvcToken('');
      load(true);
    } catch (e) { Alert.alert('error', `${e.message}`); }
    setBusy(null);
  };

  const statusText = (c) =>
    !c.enabled ? 'Off' : c.status === 'connected' ? `${c.unread_count || 0} unread` : 'Not connected';

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <View style={styles.header}><Text style={styles.headerTitle}>Connectors</Text></View>
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} />}
      >
        <Text style={styles.lede}>
          Pick your frequent apps. Enabled connectors appear as a widget rail on
          command port with live unread badges.
        </Text>

        {loading ? (
          <ActivityIndicator style={{ marginTop: 32 }} color={colors.primary} />
        ) : (
          items.map(c => (
            <View key={c.id}>
              <View style={styles.row}>
                <View style={[styles.icon, { backgroundColor: c.color || colors.primary }]}>
                  <Ionicons name={BRAND_ICON[c.id] ?? 'link'} size={20} color="#fff" />
                </View>
                <View style={styles.meta}>
                  <Text style={styles.name}>{c.name}</Text>
                  <Text style={styles.status}>{statusText(c)}</Text>
                </View>
                {c.enabled && (c.unread_count || 0) > 0 && (
                  <View style={styles.badge}>
                    <Text style={styles.badgeTxt}>{c.unread_count > 99 ? '99+' : c.unread_count}</Text>
                  </View>
                )}
                {busy === c.id ? (
                  <ActivityIndicator color={colors.primary} />
                ) : (
                  <Switch
                    value={!!c.enabled}
                    onValueChange={v => toggle(c.id, v)}
                    trackColor={{ true: colors.primary, false: colors.border }}
                    thumbColor="#fff"
                  />
                )}
              </View>
              {!c.connected && showToken === c.id && (
                <View style={styles.pairRow}>
                  <Text style={styles.hint}>{c.hint || 'Paste a token to pair.'}</Text>
                </View>
              )}
              {!c.connected && (
                <TouchableOpacity onPress={() => showToken === c.id ? pair(c.id) : setShowToken(c.id)}>
                  <Text style={styles.pairLink}>{showToken === c.id ? 'Tap again to Pair (token pasted below)' : 'Pair / connect'}</Text>
                </TouchableOpacity>
              )}
            </View>
          ))
        )}

        <Text style={styles.tokenLabel}>Service token (paste, then tap Pair on a row)</Text>
        <TextInput style={styles.tokenInput} value={svcToken} onChangeText={setSvcToken}
          placeholder="paste service token" placeholderTextColor={colors.sub} autoCapitalize="none" />

        <View style={styles.card}>
          <Text style={styles.cardTitle}>About live counts</Text>
          <Text style={styles.cardSub}>
            Badges show real unread counts only once a provider is connected
            (OAuth / token / pairing). Until then providers stay
            “Not connected” with a count of 0 — never estimated.
          </Text>
        </View>

        <View style={{ height: insets.bottom + 20 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { paddingHorizontal: spacing.lg, paddingVertical: 14, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  content: { padding: spacing.lg },
  lede: { fontSize: 13, color: colors.sub, marginBottom: 14, lineHeight: 19 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 10 },
  icon: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  meta: { flex: 1, gap: 2 },
  name: { fontSize: 15, fontWeight: '600', color: colors.text },
  status: { fontSize: 12, color: colors.sub },
  badge: { minWidth: 22, height: 22, paddingHorizontal: 6, borderRadius: 11, backgroundColor: colors.error, alignItems: 'center', justifyContent: 'center' },
  badgeTxt: { color: '#fff', fontSize: 12, fontWeight: '700' },
  pairRow: { backgroundColor: colors.surface, borderRadius: radius.md, padding: 10, marginBottom: 6 },
  hint: { fontSize: 12, color: colors.sub },
  pairLink: { color: colors.primary, fontSize: 13, marginBottom: 12, marginLeft: 4 },
  tokenLabel: { fontSize: 12, color: colors.sub, marginTop: 8 },
  tokenInput: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 12, color: colors.text },
  card: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: 14, marginTop: 12 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: colors.text, marginBottom: 4 },
  cardSub: { fontSize: 12, color: colors.sub, lineHeight: 17 },
});

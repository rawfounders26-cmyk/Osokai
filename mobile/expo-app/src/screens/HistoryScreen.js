// Osok-AI History — Monthly Usage: graph + swipeable folder stack + goals.
import { useState, useEffect, useCallback, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, RefreshControl, ScrollView, Animated } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { listMonths, getMonthDetail, onSync } from '../services/api';
import { colors, radius, spacing } from '../services/theme';
import { UsageGraph } from '../components/history/MonthGraph';
import { FolderStack } from '../components/history/FolderStack';
import { accentForMonth, shortLabel } from '../components/history/MonthFolder';

export default function HistoryScreen() {
  const insets = useSafeAreaInsets();
  const [months, setMonths] = useState([]);
  const [front, setFront] = useState(null);
  const [selected, setSelected] = useState(null);
  const [envelopeOpen, setEnvelopeOpen] = useState(false);
  const [detail, setDetail] = useState({});
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const openAnim = useRef(new Animated.Value(0)).current;
  const detailRef = useRef(detail);
  detailRef.current = detail;

  const loadDetail = useCallback(async (ym) => {
    setLoadingDetail(true);
    try {
      const d = await getMonthDetail(ym);
      setDetail(prev => ({ ...prev, [ym]: d }));
    } catch {}
    setLoadingDetail(false);
  }, []);

  const load = useCallback(async () => {
    try {
      const list = await listMonths();
      setMonths(list);
      setError(null);
      const newest = list[list.length - 1]?.month ?? list[0]?.month ?? null;
      setFront(prev => prev ?? newest);
      setSelected(prev => prev ?? newest);
      if (newest && !detailRef.current[newest]) await loadDetail(newest);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load history');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [loadDetail]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => onSync(() => load()), [load]);
  useEffect(() => {
    Animated.timing(openAnim, { toValue: envelopeOpen && selected ? 1 : 0, duration: 280, useNativeDriver: false }).start();
  }, [envelopeOpen, selected, openAnim]);

  const openFolder = (ym) => {
    if (ym === selected && envelopeOpen) { setEnvelopeOpen(false); return; }
    setSelected(ym);
    setEnvelopeOpen(true);
    if (!detailRef.current[ym]) loadDetail(ym);
  };

  const shownYm = selected ?? front;
  const shownFolder = months.find(m => m.month === shownYm) ?? months[months.length - 1] ?? null;
  const shownDetail = shownYm ? detail[shownYm] ?? null : null;
  const accent = shownFolder ? accentForMonth(months, shownFolder.month) : colors.primary;

  if (loading) {
    return (
      <View style={[st.container, { paddingTop: insets.top }]}>
        <View style={st.header}><Text style={st.headerTitle}>Monthly Usage</Text></View>
        <View style={st.center}><ActivityIndicator size="large" color={colors.primary} /></View>
      </View>
    );
  }
  if (error || !shownFolder) {
    return (
      <View style={[st.container, { paddingTop: insets.top }]}>
        <View style={st.header}><Text style={st.headerTitle}>Monthly Usage</Text></View>
        <View style={st.center}>
          <Text style={st.emptyTitle}>Couldn't reach the server</Text>
          <Text style={st.emptySub}>{error ?? 'No usage yet'}</Text>
          <TouchableOpacity style={st.retry} onPress={() => { setLoading(true); load(); }}>
            <Text style={st.retryTxt}>Retry</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  const goals = shownDetail?.goals ?? [];
  return (
    <View style={[st.container, { paddingTop: insets.top }]}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={st.page}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); setDetail({}); load(); }} tintColor={colors.primary} />}>
        <View style={st.topCard}>
          <View style={st.topRow}>
            <Text style={st.topTitle}>Monthly Usage</Text>
            <TouchableOpacity onPress={() => { setRefreshing(true); setDetail({}); load(); }} style={st.refreshBtn}>
              <Text style={st.refreshTxt}>↻</Text>
            </TouchableOpacity>
          </View>
          <Text style={[st.topPct, { color: accent }]}>{shownFolder.tasks} goals</Text>
          <Text style={st.topSub}>{shortLabel(shownFolder.month)} · {shownFolder.usage}</Text>
          <View style={st.graphWrap}>
            {shownDetail ? (
              <UsageGraph values={shownDetail.days.map(d => d.total)} accent={accent} />
            ) : (
              <View style={st.graphLoading}>
                {loadingDetail ? <ActivityIndicator color={colors.primary} /> : <Text style={st.emptySub}>Tap {shortLabel(shownFolder.month)} to load the graph</Text>}
              </View>
            )}
          </View>
        </View>

        <View style={st.stackGap}>
          <FolderStack months={months} front={front} onFrontChange={setFront} onOpen={openFolder} locked={envelopeOpen} />
        </View>

        <Animated.View style={[st.envelope, {
          opacity: openAnim,
          maxHeight: openAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 2000] }),
          transform: [{ translateY: openAnim.interpolate({ inputRange: [0, 1], outputRange: [-16, 0] }) }],
        }]}>
          <View style={st.papersBox}>
            <Text style={st.deckHint}>
              {goals.length ? `${goals.length} goals in ${shownYm} — newest first` : loadingDetail ? 'Opening folder…' : 'No goals yet'}
            </Text>
            {goals.map((g, j) => (
              <Text key={j} style={st.goal}>• {g.text}</Text>
            ))}
          </View>
        </Animated.View>
      </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  page: { paddingBottom: 32 },
  header: { paddingHorizontal: spacing.lg, paddingVertical: 14, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  topCard: { margin: spacing.md, marginBottom: 4, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: 14, gap: 4 },
  topRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  topTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  topPct: { fontSize: 26, fontWeight: '800' },
  topSub: { fontSize: 12, color: colors.sub },
  refreshBtn: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.border },
  refreshTxt: { fontSize: 16, color: colors.sub, fontWeight: '700' },
  graphWrap: { marginTop: 8, alignItems: 'center', minHeight: 120, justifyContent: 'center' },
  graphLoading: { height: 120, alignItems: 'center', justifyContent: 'center' },
  stackGap: { marginTop: 110 },
  envelope: { overflow: 'hidden', paddingHorizontal: spacing.md },
  papersBox: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: 12, gap: 8 },
  deckHint: { fontSize: 11, color: colors.sub },
  goal: { fontSize: 13, color: colors.text, lineHeight: 19 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10, padding: spacing.xl },
  emptySub: { fontSize: 14, color: colors.sub, textAlign: 'center' },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  retry: { marginTop: 6, paddingHorizontal: 20, paddingVertical: 10, backgroundColor: colors.primary, borderRadius: radius.full },
  retryTxt: { color: '#fff', fontWeight: '700' },
});

// Osok-AI backend client — mirrors osokai mobile's services/api pattern.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { loadConfig } from './config';

const QUEUE_KEY = 'osokai_offline_queue';

function isNetErr(e) {
  const m = `${e && e.message || e}`;
  return /network request failed|failed to fetch|network error|aborted|timed out/i.test(m);
}

export async function queueLength() {
  try {
    const q = JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) || '[]');
    return q.length;
  } catch { return 0; }
}

async function enqueue(path, body) {
  try {
    const q = JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) || '[]');
    q.push({ path, body, ts: Date.now() });
    await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(q.slice(-50)));
  } catch {}
}

export async function flushQueue() {
  let q = [];
  try { q = JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) || '[]'); } catch {}
  if (!q.length) return 0;
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const left = [];
  let sent = 0;
  for (const item of q) {
    try {
      await fetch(`${base}${item.path}`, { method: 'POST', headers: hdrs, body: JSON.stringify(item.body) });
      sent++; // any HTTP answer counts as delivered (even 4xx: server saw it)
    } catch (e) {
      if (isNetErr(e)) { left.push(item); break; } // still offline: keep rest
      sent++;
    }
  }
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(left));
  return sent;
}

async function headers() {
  const cfg = await loadConfig();
  const h = { 'Content-Type': 'application/json' };
  if (cfg.authToken) h['Authorization'] = `Bearer ${cfg.authToken}`;
  return h;
}

async function baseUrl() {
  const cfg = await loadConfig();
  return cfg.serverUrl || 'http://127.0.0.1:8765';
}

async function throwDetail(res, fallback) {
  let detail = fallback;
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') detail = body.detail;
  } catch {}
  throw new Error(detail);
}

export async function health() {
  const base = await baseUrl();
  const res = await fetch(`${base}/health`);
  return res.json();
}

export async function authCheck() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/auth-check`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function pairRedeem(code) {
  const cfg = await loadConfig();
  const base = (cfg.serverUrl || process.env.EXPO_PUBLIC_API_BASE_URL || '').trim();
  if (!base) throw new Error('enter Backend URL first (pairing needs a server to ask)');
  const res = await fetch(`${base}/pairing/redeem`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function chat(message) {
  const [base, hdrs, cfg] = await Promise.all([baseUrl(), headers(), loadConfig()]);
  const body = { message, device: cfg.device || 'mobile-app' };
  try {
    const res = await fetch(`${base}/chat`, { method: 'POST', headers: hdrs, body: JSON.stringify(body) });
    if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
    flushQueue().catch(() => {});
    return res.json();
  } catch (e) {
    if (isNetErr(e)) {
      await enqueue('/chat', body);
      return { reply: '📴 offline — queued, will send when back online.', approval_required: false, queued: true };
    }
    throw e;
  }
}

export async function getTasks() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/tasks`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function getFiles(sub = '') {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/files${sub ? `?path=${encodeURIComponent(sub)}` : ''}`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function getInbox() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/inbox`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function getConnectors() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/connectors`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function connectService(id, token) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/connectors/${id}/connect`, {
    method: 'POST', headers: hdrs, body: JSON.stringify({ token }),
  });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function disconnectService(id) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/connectors/${id}/disconnect`, { method: 'POST', headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function setConnectorEnabled(id, enabled) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/connectors/${id}`, {
    method: 'PATCH', headers: hdrs, body: JSON.stringify({ enabled }),
  });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function listPendingApprovals() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/approvals`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  const body = await res.json();
  return body?.pending ?? [];
}

export async function decideApproval(id, allow) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/approvals/${id}/resolve`, {
    method: 'POST', headers: hdrs, body: JSON.stringify({ allow }),
  });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function voiceTranscribe(uri) {
  const cfg = await loadConfig();
  const base = cfg.serverUrl || 'http://127.0.0.1:8765';
  const headers = {};
  if (cfg.authToken) headers['Authorization'] = `Bearer ${cfg.authToken}`;
  const form = new FormData();
  form.append('file', { uri, name: 'voice.m4a', type: 'audio/m4a' });
  const res = await fetch(`${base}/voice/transcribe`, { method: 'POST', headers, body: form });
  if (!res.ok) return '';
  const j = await res.json();
  return j.text || '';
}

export async function listMonths() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/history/months`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  const body = await res.json();
  return body?.months ?? [];
}

export async function getMonthDetail(yearMonth) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/history/months/${encodeURIComponent(yearMonth)}`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function buildSyncUrl() {
  const cfg = await loadConfig();
  const base = (cfg.serverUrl || 'http://127.0.0.1:8765').replace(/^http/, 'ws');
  const token = cfg.authToken ? `?token=${encodeURIComponent(cfg.authToken)}` : '';
  return `${base}/ws/sync${token}`;
}

export async function billGroups() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/bills/groups`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function billExpense(gid, title, amount, paidBy, splits) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/bills/expenses`, {
    method: 'POST', headers: hdrs,
    body: JSON.stringify({ gid, title, amount, paid_by: paidBy, splits: splits || {} }),
  });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function billBalances(gid) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/bills/balances/${gid}`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function billSettle(gid, frm, to, amount) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/bills/settle`, {
    method: 'POST', headers: hdrs, body: JSON.stringify({ gid, frm, to, amount }),
  });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function billActivity(gid) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/bills/activity/${gid}`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function wardrobeItems() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/wardrobe/items`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function wardrobeAdd(item) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/wardrobe/items`, { method: 'POST', headers: hdrs, body: JSON.stringify(item) });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function wardrobeSuggest(formality = '') {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/wardrobe/suggest${formality ? `?formality=${encodeURIComponent(formality)}` : ''}`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function wardrobeFeedback(id, good, note = '') {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/wardrobe/feedback`, { method: 'POST', headers: hdrs, body: JSON.stringify({ id, good, note }) });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function wardrobeWorn(id) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/wardrobe/worn/${id}`, { method: 'POST', headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function wardrobePrefs() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/wardrobe/prefs`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function loopsList(status = '') {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/loops${status ? `?status=${status}` : ''}`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function loopClose(id) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/loops/${id}/close`, { method: 'POST', headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function loopSnooze(approvalId, hours = 3) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/loops/from-approval/${approvalId}`, {
    method: 'POST', headers: hdrs, body: JSON.stringify({ hours }),
  });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function notifications() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/notifications`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export async function pendingApprovals() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/approvals`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  const j = await res.json();
  return j.pending || [];
}

export async function loopsDue() {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}/loops/due`, { headers: hdrs });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  const j = await res.json();
  return j.due || [];
}

async function vault(path, opts = {}) {
  const [base, hdrs] = await Promise.all([baseUrl(), headers()]);
  const res = await fetch(`${base}${path}`, { headers: hdrs, ...opts });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
}

export const vaultStatus = () => vault('/vault/status');
export const vaultLock = () => vault('/vault/lock', { method: 'POST' });
export const vaultUnlock = (minutes = 15) =>
  vault('/vault/unlock', { method: 'POST', body: JSON.stringify({ minutes }) });
export const vaultList = () => vault('/vault/list');
export const vaultAudit = (limit = 15) => vault(`/vault/audit?limit=${limit}`);
export const vaultPolicy = (key, policy, domains) =>
  vault('/vault/policy', { method: 'POST', body: JSON.stringify({ key, policy, domains }) });
export const vaultTotp = (key, domain = '') =>
  vault('/vault/totp', { method: 'POST', body: JSON.stringify({ key, domain }) });

// live sync: one socket per app session, backoff reconnect, heartbeat-safe
let syncSock = null;
let syncDelay = 5000;
const syncListeners = new Set();
export function onSync(cb) {
  syncListeners.add(cb);
  return () => syncListeners.delete(cb);
}
export async function startSync() {
  try { if (syncSock) syncSock.close(); } catch {}
  const cfg = await loadConfig();
  if (!cfg.authToken) return; // not connected yet — stay silent, don't burn lockout
  const url = await buildSyncUrl();
  const ws = new WebSocket(url);
  syncSock = ws;
  ws.onopen = () => { syncDelay = 5000; flushQueue().catch(() => {}); };
  ws.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.ping) return;
      syncListeners.forEach(cb => { try { cb(d); } catch {} });
    } catch {}
  };
  ws.onclose = () => { syncDelay = Math.min(syncDelay * 2, 30000); setTimeout(startSync, syncDelay); };
  ws.onerror = () => { try { ws.close(); } catch {} };
}

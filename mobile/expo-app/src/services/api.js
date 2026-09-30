// Osok-AI backend client — mirrors osokai mobile's services/api pattern.
import { loadConfig } from './config';

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

export async function chat(message) {
  const [base, hdrs, cfg] = await Promise.all([baseUrl(), headers(), loadConfig()]);
  const res = await fetch(`${base}/chat`, {
    method: 'POST', headers: hdrs,
    body: JSON.stringify({ message, device: cfg.device || 'mobile-app' }),
  });
  if (!res.ok) await throwDetail(res, `HTTP ${res.status}`);
  return res.json();
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
  ws.onopen = () => { syncDelay = 5000; };
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

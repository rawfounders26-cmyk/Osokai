// Osok-AI extension service worker — tab summarize + live approval badge.
async function cfg() {
  const d = await chrome.storage.local.get(['OSOKAI_base', 'OSOKAI_token']);
  return { base: d.OSOKAI_base || 'http://127.0.0.1:8765', token: d.OSOKAI_token || '' };
}
chrome.runtime.onMessage.addListener((msg, s, send) => {
  if (msg.type === 'OSOKAI_SEND_TAB') {
    (async () => {
      const c = await cfg();
      const headers = { 'Content-Type': 'application/json' };
      if (c.token) headers['Authorization'] = 'Bearer ' + c.token;
      const r = await fetch(c.base + '/chat', { method: 'POST', headers, body: JSON.stringify({ message: 'Summarize this tab: ' + msg.text.slice(0, 4000), device: msg.device || 'laptop-chrome' }) });
      if (r.status === 401) return send({ reply: 'wrong Osok-AI token — paste it in popup Settings' });
      const j = await r.json();
      send({ reply: j.reply });
      pollBadge();
    })();
    return true;
  }
});
async function pollBadge() {
  try {
    const c = await cfg();
    if (!c.token) { chrome.action.setBadgeText({ text: '' }); return; }
    const headers = {};
    if (c.token) headers['Authorization'] = 'Bearer ' + c.token;
    const [a, n] = await Promise.all([
      fetch(c.base + '/approvals', { headers }).then((r) => (r.ok ? r.json() : { pending: [] })).catch(() => ({ pending: [] })),
      fetch(c.base + '/notifications', { headers }).then((r) => (r.ok ? r.json() : { unread: 0 })).catch(() => ({ unread: 0 })),
    ]);
    const total = (a.pending || []).length + (n.unread || 0);
    chrome.action.setBadgeText({ text: total ? String(total) : '' });
    chrome.action.setBadgeBackgroundColor({ color: '#d61f26' });
  } catch (e) {}
}
chrome.alarms.create('osokai-poll', { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((a) => { if (a.name === 'osokai-poll') pollBadge(); });
chrome.runtime.onStartup.addListener(pollBadge);
chrome.runtime.onInstalled.addListener(pollBadge);

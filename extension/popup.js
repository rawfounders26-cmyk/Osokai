// Osok-AI popup — Connection (URL + Device ID + token) + approvals + summarize. Dark UI.
async function cfg() {
  const d = await chrome.storage.local.get(['OSOKAI_base', 'OSOKAI_token', 'OSOKAI_device']);
  return { base: d.OSOKAI_base || 'http://127.0.0.1:8765', token: d.OSOKAI_token || '', device: d.OSOKAI_device || 'laptop-chrome' };
}
async function authed(path, opts) {
  const c = await cfg();
  const headers = { 'Content-Type': 'application/json' };
  if (c.token) headers['Authorization'] = 'Bearer ' + c.token;
  const r = await fetch(c.base + path, { ...(opts || {}), headers });
  if (r.status === 401) throw new Error('wrong token — paste it below');
  if (!r.ok) throw new Error('backend ' + r.status);
  return r.json();
}
async function loadApprovals() {
  const box = document.getElementById('alist'), head = document.getElementById('appr');
  try {
    const j = await authed('/approvals');
    const p = j.pending || [];
    box.innerHTML = '';
    if (!p.length) { head.textContent = 'No pending approvals.'; head.classList.remove('has'); return; }
    head.textContent = `${p.length} pending approval${p.length > 1 ? 's' : ''}.`;
    head.classList.add('has');
    p.forEach((a) => {
      const el = document.createElement('div'); el.className = 'aitem';
      const isPay = a.kind === 'payment';
      const title = isPay ? `💳 Payment — ${a.item || a.message}` : `#${a.id} ${a.message}`;
      el.innerHTML = `<div class="m"><b>${title}</b> <span style="color:#8a8a96">(${a.device})</span></div>`;
      const row = document.createElement('div'); row.className = 'row';
      const ok = document.createElement('button'); ok.className = 'allow'; ok.textContent = 'Allow';
      const no = document.createElement('button'); no.className = 'deny'; no.textContent = 'Deny';
      ok.onclick = async () => { await authed(`/approvals/${a.id}/resolve`, { method: 'POST', body: JSON.stringify({ allow: true }) }); loadApprovals(); };
      no.onclick = async () => { await authed(`/approvals/${a.id}/resolve`, { method: 'POST', body: JSON.stringify({ allow: false }) }); loadApprovals(); };
      row.appendChild(ok); row.appendChild(no); el.appendChild(row);
      const later = document.createElement('button'); later.textContent = 'Later → loop';
      later.onclick = async () => { await authed(`/loops/from-approval/${a.id}`, { method: 'POST', body: JSON.stringify({ hours: 3 }) }); loadApprovals(); };
      el.appendChild(later);
      if (isPay) {
        const fill = document.createElement('button'); fill.className = 'fill'; fill.textContent = 'Autofill payment on this page';
        fill.onclick = async () => {
          document.getElementById('o').textContent = await fillFields(['card_number', 'card_expiry', 'card_cvv', 'card_name'], { card_number: 'number', card_expiry: 'expiry', card_cvv: 'cvv', card_name: 'name' });
        };
        el.appendChild(fill);
      } box.appendChild(el);
    });
  } catch (e) { head.textContent = e.message; }
}
(async () => {
  const c = await cfg();
  document.getElementById('base').value = c.base;
  document.getElementById('tok').value = c.token;
  document.getElementById('dev').value = c.device;
  loadApprovals();
  loadVaultBar();
})();
document.getElementById('save').onclick = async () => {
  const base = document.getElementById('base').value.trim() || 'http://127.0.0.1:8765';
  const token = document.getElementById('tok').value.trim();
  const device = document.getElementById('dev').value.trim() || 'laptop-chrome';
  await chrome.storage.local.set({ OSOKAI_base: base, OSOKAI_token: token, OSOKAI_device: device });
  try {
    await authed('/auth-check');
    document.getElementById('o').textContent = 'live + synced ✓';
  } catch (e) { document.getElementById('o').textContent = e.message; }
  loadApprovals();
};
async function activeDomain() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    return { tab, domain: new URL(tab.url).hostname };
  } catch (e) { return { tab: null, domain: '' }; }
}
async function fillFields(keys, map) {
  // decrypt from vault (authed, domain-checked) -> inject into active tab fields (memory only)
  try {
    const { tab, domain } = await activeDomain();
    if (!tab) return 'no active tab';
    const fields = {};
    for (const k of keys) {
      try {
        const j = await authed('/vault/fill', { method: 'POST', body: JSON.stringify({ key: k, domain, device: 'extension' }) });
        if (j.value) fields[map[k]] = j.value;
      } catch (e) { return `${k}: ${e.message}`; }
    }
    if (!Object.keys(fields).length) return 'no saved values for: ' + keys.join(', ');
    const res = await chrome.tabs.sendMessage(tab.id, { type: 'OSOKAI_FILL', fields });
    return 'filled: ' + JSON.stringify(res?.filled || {});
  } catch (e) { return 'fill failed: ' + e.message; }
}
async function loadVaultBar() {
  try {
    const st = await authed('/vault/status');
    const lock = await authed('/vault/list');
    const pks = (lock.secrets || []).filter(s => s.scope === 'passkey');
    document.getElementById('lockstate').textContent = st.locked ? 'vault 🔒' : 'vault open';
    const box = document.getElementById('pklist');
    box.innerHTML = '';
    pks.forEach(p => {
      const b = document.createElement('button');
      b.textContent = '🔑 ' + p.key.replace('passkey:', '');
      b.onclick = async () => {
        const { tab } = await activeDomain();
        if (!tab) return;
        const fill = await authed('/vault/fill', { method: 'POST', body: JSON.stringify({ key: p.key, device: 'extension' }) });
        const res = await chrome.tabs.sendMessage(tab.id, { type: 'OSOKAI_PK', credentialId: fill.value });
        document.getElementById('o').textContent = res?.ok ? 'passkey accepted ✓' : ('passkey: ' + (res?.error || 'failed'));
      };
      box.appendChild(b);
    });
  } catch (e) {}
}
document.getElementById('lockbtn').onclick = async () => {
  try {
    const st = await authed('/vault/status');
    if (st.locked) await authed('/vault/unlock', { method: 'POST', body: JSON.stringify({ minutes: 15 }) });
    else await authed('/vault/lock', { method: 'POST' });
  } catch (e) { document.getElementById('o').textContent = e.message; }
  loadVaultBar();
};
document.getElementById('filllogin').onclick = async () => {
  document.getElementById('o').textContent = await fillFields(['login_user', 'login_pass'], { login_user: 'username', login_pass: 'password' });
};
document.getElementById('filltotp').onclick = async () => {
  try {
    const { domain } = await activeDomain();
    const seeds = await authed('/vault/list');
    const seed = (seeds.secrets || []).find(s => s.key.toLowerCase().includes('totp') || s.key.toLowerCase().includes('otp'));
    if (!seed) { document.getElementById('o').textContent = 'no TOTP seed stored (save one as *totp*)'; return; }
    const j = await authed('/vault/totp', { method: 'POST', body: JSON.stringify({ key: seed.key, domain }) });
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const res = await chrome.tabs.sendMessage(tab.id, { type: 'OSOKAI_FILL', fields: { totp: j.code } });
    document.getElementById('o').textContent = res?.filled?.totp ? `TOTP filled (${j.code})` : 'no OTP field found';
  } catch (e) { document.getElementById('o').textContent = e.message; }
};
document.getElementById('saveloop').onclick = async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const j = await authed('/loops', { method: 'POST', body: JSON.stringify({ kind: 'save', title: `${tab.title} — ${tab.url}`, source: 'extension' }) });
    document.getElementById('o').textContent = `saved as loop #${j.id} ✓`;
  } catch (e) { document.getElementById('o').textContent = e.message; }
};
document.getElementById('go').onclick = async () => {
  const o = document.getElementById('o');
  try {
    const c = await cfg();
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    o.textContent = 'reading tab…';
    const r = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => document.body.innerText.slice(0, 6000) });
    o.textContent = 'thinking…';
    chrome.runtime.sendMessage({ type: 'OSOKAI_SEND_TAB', text: r[0].result, device: c.device }, (res) => {
      o.textContent = res?.reply || 'no backend? start backend first';
    });
  } catch (e) { o.textContent = e.message; }
  loadApprovals();
};

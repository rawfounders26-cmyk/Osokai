// Osok-AI Command Port — one global Backend URL + Auth Token (Settings ⚙), sent on every call.
const cfg = {
  get base() { return localStorage.getItem('OSOKAI_base') || window.osokai.apiBase; },
  get token() { return localStorage.getItem('OSOKAI_token') || ''; },
  set(base, token) { localStorage.setItem('OSOKAI_base', base); localStorage.setItem('OSOKAI_token', token); },
};
async function pfetch(path, opts) {
  opts = opts || {};
  opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
  if (cfg.token) opts.headers['Authorization'] = 'Bearer ' + cfg.token;
  const r = await fetch(cfg.base + path, opts);
  if (r.status === 401) throw new Error('wrong Osok-AI token — paste it in ⚙ Settings');
  if (!r.ok) throw new Error('backend ' + r.status);
  return r.json();
}
const q = document.getElementById('q'), out = document.getElementById('out');
// live sync: backend pushes on every mutation (chat/connect/approval/notes) — all surfaces stay identical
let ws = null, wsDelay = 5000;
function wsConnect() {
  if (!cfg.token) { out.textContent = 'paste your Osok-AI token in ⚙ Settings → Connect, then I go live.'; return; }
  try { if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return; } catch (e) {}
  try { if (ws) ws.close(); } catch (e) {}
  try {
    ws = new WebSocket(cfg.base.replace(/^http/, 'ws') + '/ws/sync?token=' + encodeURIComponent(cfg.token));
    ws.onopen = () => { wsDelay = 5000; };
    ws.onmessage = (ev) => {
      try { if (JSON.parse(ev.data).ping) return; } catch (e) {}
      refreshConnectors(); checkNotes();
    };
    ws.onclose = (ev) => { console.log('Osok-AI ws closed', ev.code, ev.reason); wsDelay = Math.min(wsDelay * 2, 30000); setTimeout(wsConnect, wsDelay); };
  } catch (e) { setTimeout(wsConnect, 5000); }
}
async function refreshConnectors() {
  if (!cfg.token) return;
  try {
    const j = await pfetch('/connectors');
    (j.connectors || []).forEach(c => {
      const el = document.querySelector('#dots-panel button.conn[data-c="' + c.id + '"]');
      if (el) {
        el.classList.toggle('on', !!c.connected);
        const name = el.title.replace(/ \(connected\)$/, '');
        el.title = c.connected ? name + ' (connected)' : name;
      }
    });
  } catch (e) { out.textContent = e.message; }
}
document.getElementById('dots').onclick = () => {
  const p = document.getElementById('dots-panel');
  p.classList.toggle('open');
  window.osokai.resize(p.classList.contains('open') ? 'open' : 'hide');
  refreshConnectors();
};
document.getElementById('btn-close').onclick = () => window.osokai.hide();
document.getElementById('btn-min').onclick = () => { document.body.classList.add('mini'); window.osokai.mini(); checkNotes(); };
window.osokai.onDock((side) => {
  document.body.classList.remove('dock-right', 'dock-left', 'dock-top', 'dock-bottom', 'dock-float');
  (side || 'float').split(' ').forEach(s => document.body.classList.add('dock-' + s));
});
document.getElementById('agentBtn').onclick = () => { document.body.classList.remove('mini'); window.osokai.restore(); };
document.getElementById('bellBtn').onclick = async () => {
  document.body.classList.remove('mini'); window.osokai.restore();
  try {
    const j = await pfetch('/inbox');
    out.textContent = 'inbox: ' + (j.summary ? j.summary.briefing : JSON.stringify(j));
  } catch (e) { out.textContent = e.message; }
  try { await pfetch('/notifications/simulate', { method: 'POST', body: JSON.stringify({ unread: 0 }) }); } catch (e) {}
  checkNotes();
};
async function checkNotes() {
  if (!cfg.token) return;
  try {
    const j = await pfetch('/notifications');
    const b = document.getElementById('bellBtn');
    const n = j.unread || 0;
    b.classList.toggle('alert', n > 0);
    document.getElementById('bellCount').textContent = n > 9 ? '9+' : String(n);
    if (n > 0) b.title = 'Notifications: ' + n + ' new' + (j.from ? ' from ' + j.from : '');
    else b.title = 'Notifications';
  } catch (e) { /* offline */ }
}
setInterval(checkNotes, 15000);
q.addEventListener('keydown', (e) => { if (e.key === 'Enter') document.getElementById('send').click(); });
document.getElementById('send').onclick = async () => {
  out.textContent = 'thinking...';
  try {
    const j = await pfetch('/chat', { method: 'POST', body: JSON.stringify({ message: q.value, device: 'command-port' }) });
    out.textContent = j.reply;
  } catch (e) { out.textContent = e.message; }
};
let consoleOpen = false;
document.getElementById('shot').onclick = async () => {
  // 📷 = takeover console: live screenshot of the VM browser Osok-AI drives
  if (consoleOpen) { out.innerHTML = ''; out.style.maxHeight = '60px'; consoleOpen = false; window.osokai.resize('hide'); return; }
  out.textContent = 'opening console…';
  try {
    const headers = {};
    if (cfg.token) headers['Authorization'] = 'Bearer ' + cfg.token;
    const r = await fetch(cfg.base + '/browser/screenshot', { headers });
    if (!r.ok) throw new Error('console failed: ' + r.status);
    const url = URL.createObjectURL(await r.blob());
    out.innerHTML = '';
    const img = document.createElement('img');
    img.src = url; img.style.cssText = 'max-width:100%;max-height:260px;border-radius:8px;';
    out.appendChild(img);
    const st = await pfetch('/browser/state').catch(() => null);
    if (st && st.state) { const d = document.createElement('div'); d.textContent = st.state.slice(0, 400); out.appendChild(d); }
    out.style.maxHeight = '320px';
    consoleOpen = true;
    window.osokai.resize('open');
  } catch (e) { out.textContent = e.message; }
};
document.querySelectorAll('#dots-panel button[data-c]').forEach(b => b.onclick = async () => {
  const cid = b.dataset.c;
  try {
    const token = prompt('Paste ' + cid + ' service token (Cancel = view hint):');
    if (token) {
      const j = await pfetch('/connectors/' + cid + '/connect', { method: 'POST', body: JSON.stringify({ token }) });
      out.textContent = cid + ': ' + JSON.stringify(j);
    } else {
      const j = await pfetch('/connectors/' + cid + '/auth-url');
      out.textContent = cid + ' hint: ' + (j.hint || j.auth_url);
    }
  } catch (e) { out.textContent = e.message; }
  refreshConnectors();
});
document.getElementById('more').onclick = () => { out.textContent = '+ Add more: Telegram, Teams, LinkedIn, Instagram — coming next.'; };
async function loadSettings() {
  // global connection block
  document.getElementById('set-base').value = cfg.base;
  document.getElementById('set-token').value = cfg.token;
  const box = document.getElementById('settings-rows');
  try {
    const j = await pfetch('/connectors');
    box.innerHTML = '';
    (j.connectors || []).forEach(c => {
      const row = document.createElement('div'); row.className = 'srow';
      row.innerHTML = '<img src="icons/' + c.id + '.svg" alt="' + c.id + '"><input id="tok-' + c.id + '" type="password" placeholder="' + c.id + (c.connected ? ' (connected)' : ' service token') + '">';
      const save = document.createElement('button'); save.textContent = c.connected ? 'Update' : 'Save';
      save.onclick = async () => {
        const token = document.getElementById('tok-' + c.id).value.trim();
        if (!token) { out.textContent = c.id + ': paste a token first'; return; }
        try {
          const jj = await pfetch('/connectors/' + c.id + '/connect', { method: 'POST', body: JSON.stringify({ token }) });
          out.textContent = c.id + ': ' + JSON.stringify(jj);
        } catch (e) { out.textContent = e.message; }
        refreshConnectors(); loadSettings();
      };
      const clear = document.createElement('button'); clear.textContent = '✕'; clear.title = 'Disconnect';
      clear.onclick = async () => {
        try {
          const jj = await pfetch('/connectors/' + c.id + '/disconnect', { method: 'POST' });
          out.textContent = c.id + ': ' + JSON.stringify(jj);
        } catch (e) { out.textContent = e.message; }
        refreshConnectors(); loadSettings();
      };
      row.appendChild(save); row.appendChild(clear); box.appendChild(row);
    });
    document.getElementById('settings-api').textContent = 'API: ' + cfg.base;
    loadVault();
  } catch (e) { box.innerHTML = e.message; }
}
async function loadVault() {
  // lock state
  try {
    const st = await pfetch('/vault/status');
    document.getElementById('lockstate').textContent = 'vault: ' + (st.locked ? '🔒 locked' : `unlocked (${st.seconds_left}s)`);
  } catch (e) { document.getElementById('lockstate').textContent = 'vault: ?'; }
  // secrets with policy + domains
  const vb = document.getElementById('vault-rows');
  try {
    const j = await pfetch('/vault/list');
    vb.innerHTML = '';
    (j.secrets || []).forEach(s => {
      const row = document.createElement('div'); row.className = 'srow';
      const nm = document.createElement('span'); nm.style.fontSize = '12px'; nm.textContent = `${s.key} (${s.masked})`;
      const pol = document.createElement('button'); pol.textContent = s.policy || 'while-unlocked'; pol.title = 'tap to cycle policy';
      const order = ['while-unlocked', 'always', 'never'];
      pol.onclick = async () => {
        const next = order[(order.indexOf(s.policy) + 1) % order.length] || 'while-unlocked';
        try { await pfetch('/vault/policy', { method: 'POST', body: JSON.stringify({ key: s.key, policy: next }) }); } catch (e) { out.textContent = e.message; }
        loadVault();
      };
      const dom = document.createElement('input'); dom.placeholder = 'domains csv'; dom.value = (s.domains || []).join(',');
      dom.onchange = async () => {
        try { await pfetch('/vault/policy', { method: 'POST', body: JSON.stringify({ key: s.key, domains: dom.value.split(',').map(x => x.trim()).filter(Boolean) }) }); } catch (e) { out.textContent = e.message; }
        loadVault();
      };
      row.appendChild(nm); row.appendChild(pol); row.appendChild(dom); vb.appendChild(row);
    });
  } catch (e) { vb.textContent = e.message; }
  // audit log
  const ab = document.getElementById('audit-rows');
  try {
    const j = await pfetch('/vault/audit?limit=15');
    ab.innerHTML = (j.audit || []).map(a => {
      const t = new Date(a.ts * 1000).toLocaleTimeString();
      return `<div>${a.allowed ? '✓' : '✕'} ${a.key} · ${a.domain || '-'} · ${a.device} · ${a.reason} · ${t}</div>`;
    }).join('') || 'no accesses yet';
  } catch (e) { ab.textContent = e.message; }
}
document.getElementById('lockbtn').onclick = async () => {
  try {
    const st = await pfetch('/vault/status');
    if (st.locked) await pfetch('/vault/unlock', { method: 'POST', body: JSON.stringify({ minutes: 15 }) });
    else await pfetch('/vault/lock', { method: 'POST' });
  } catch (e) { out.textContent = e.message; }
  loadVault();
};
document.getElementById('set-save').onclick = async () => {
  const base = document.getElementById('set-base').value.trim();
  const token = document.getElementById('set-token').value.trim();
  cfg.set(base, token);
  wsConnect(); // reconnect live sync on new URL/token
  try {
    const j = await pfetch('/auth-check');
    out.textContent = 'live + synced: ' + JSON.stringify(j);
  } catch (e) { out.textContent = e.message; }
  loadSettings(); refreshConnectors();
};
document.getElementById('gear').onclick = () => {
  const s = document.getElementById('settings');
  s.classList.toggle('open');
  if (s.classList.contains('open')) loadSettings();
};
refreshConnectors();
wsConnect();

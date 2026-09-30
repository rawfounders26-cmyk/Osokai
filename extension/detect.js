// Osok-AI captcha detector — light check on every page, acts only on markers.
// If a fill is pending for this domain and a challenge appears: mark captcha,
// notify everywhere (extension notification + backend bell/mobile pick it up).
(function () {
  function hasCaptcha() {
    const html = document.documentElement.innerHTML.slice(0, 60000);
    return /recaptcha|h-captcha|hcaptcha|cf-challenge|turnstile|g-recaptcha|captcha/i.test(html) &&
      !!document.querySelector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="challenges.cloudflare"], [data-sitekey]');
  }
  async function main() {
    if (!hasCaptcha()) return;
    let cfg = { base: 'http://127.0.0.1:8765', token: '' };
    try {
      const d = await chrome.storage.local.get(['OSOKAI_base', 'OSOKAI_token']);
      cfg = { base: d.OSOKAI_base || cfg.base, token: d.OSOKAI_token || '' };
    } catch (e) { return; }
    if (!cfg.token) return;
    const H = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + cfg.token };
    const domain = location.hostname;
    try {
      const r = await fetch(cfg.base + '/fill/pending?domain=' + encodeURIComponent(domain), { headers: H });
      if (!r.ok) return;
      const j = await r.json();
      const hit = (j.pending || [])[0];
      if (!hit || hit.status === 'captcha') return;
      await fetch(cfg.base + `/fill/${hit.id}/captcha`, { method: 'POST', headers: H });
      chrome.runtime.sendMessage({ type: 'OSOKAI_CAPTCHA', site: domain, id: hit.id });
    } catch (e) {}
  }
  if (document.readyState === 'complete') setTimeout(main, 2500);
  else window.addEventListener('load', () => setTimeout(main, 2500));
})();

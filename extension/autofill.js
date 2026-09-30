// Osok-AI vault autofill — decrypted values live in memory ONLY to fill platform fields.
// Triggered after user approval (popup Autofill button). Nothing is stored by this script.
(function () {
  function setVal(el, v) {
    if (!el || v == null) return false;
    el.focus();
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, String(v));
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }
  function pick(sels) {
    for (const s of sels) {
      const el = document.querySelector(s);
      if (el && el.offsetParent !== null) return el;
    }
    return null;
  }
  const SEL = {
    number: ['input[autocomplete="cc-number"]', 'input[name*="cardnumber" i]', 'input[name*="card-number" i]', 'input[id*="card-number" i]', 'input[placeholder*="card number" i]'],
    expiry: ['input[autocomplete="cc-exp"]', 'input[name*="expir" i]', 'input[placeholder*="expiry" i]', 'input[placeholder*="MM" i]'],
    cvv: ['input[autocomplete="cc-csc"]', 'input[name*="cvv" i]', 'input[name*="cvc" i]', 'input[placeholder*="CVV" i]'],
    name: ['input[autocomplete="cc-name"]', 'input[name*="cardholder" i]', 'input[name*="nameoncard" i]'],
    username: ['input[autocomplete="username"]', 'input[type="email"]', 'input[name*="email" i]', 'input[name*="login" i]', 'input[id*="username" i]'],
    password: ['input[autocomplete="current-password"]', 'input[type="password"]'],
    totp: ['input[autocomplete="one-time-code"]', 'input[name*="otp" i]', 'input[name*="2fa" i]', 'input[name*="totp" i]', 'input[inputmode="numeric"]'],
  };
  chrome.runtime.onMessage.addListener((msg, s, send) => {
    if (msg.type === 'OSOKAI_PK') {
      // passkey mediation: platform TPM holds the key; Osok-AI only stored the credential ID
      (async () => {
        try {
          const cred = await navigator.credentials.get({
            publicKey: {
              challenge: Uint8Array.from(atob(msg.challenge || 'cG9ydGVy'), c => c.charCodeAt(0)),
              allowCredentials: [{ id: Uint8Array.from(atob(msg.credentialId), c => c.charCodeAt(0)), type: 'public-key' }],
              userVerification: 'preferred',
            },
          });
          send({ ok: !!cred });
        } catch (e) { send({ ok: false, error: String(e && e.message || e) }); }
      })();
      return true;
    }
    if (msg.type !== 'OSOKAI_FILL') return;
    const f = msg.fields || {};
    const done = {};
    for (const k of Object.keys(SEL)) {
      if (f[k] == null) continue;
      done[k] = !!setVal(pick(SEL[k]), f[k]);
    }
    send({ filled: done });
    return true;
  });
})();

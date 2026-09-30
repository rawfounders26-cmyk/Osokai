// Osok-AI web-task completer — runs automatically, no clicks needed.
// YouTube is an SPA: hook yt-navigate-finish so search->watch transitions are caught.
(function () {
  let lastHref = '', clickedFor = '', playTimer = null;

  function firstVideo() {
    return document.querySelector('a#video-title[href^="/watch"]')
      || document.querySelector('ytd-video-renderer a#video-title');
  }
  function onResults() {
    if (clickedFor === location.href) return;
    let tries = 0;
    const t = setInterval(() => {
      tries++;
      const v = firstVideo();
      if (v) { clickedFor = location.href; clearInterval(t); v.click(); }
      else if (tries > 40) clearInterval(t);
    }, 400);
  }
  function onWatch() {
    if (playTimer) clearInterval(playTimer);
    let tries = 0;
    playTimer = setInterval(() => {
      tries++;
      const vid = document.querySelector('video');
      if (vid && vid.paused) vid.play().catch(() => {});
      if ((vid && !vid.paused) || tries > 30) clearInterval(playTimer);
    }, 700);
  }
  function route() {
    if (location.href === lastHref) return;
    lastHref = location.href;
    if (location.pathname === '/results') onResults();
    else if (location.pathname === '/watch') onWatch();
  }
  document.addEventListener('yt-navigate-finish', route);
  route();
  // fallback poll in case the event is missed
  setInterval(route, 2000);
})();

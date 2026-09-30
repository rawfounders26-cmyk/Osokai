// Osok-AI Command Port — Electron shell. Alt+Space / Option+Space toggles.
// Frameless window: drag via CSS (-webkit-app-region) in renderer.
const { app, BrowserWindow, globalShortcut, Tray, Menu, ipcMain, screen } = require('electron');
const path = require('path');
const os = require('os');
// Osok-AI needs no disk cache (localhost API + local files): keep everything in temp, no writes to protect
try {
  const dir = path.join(os.tmpdir(), 'osokai');
  app.setPath('userData', dir);
  app.commandLine.appendSwitch('disk-cache-dir', path.join(dir, 'cache'));
  app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');
} catch (e) { console.log('cache setup skipped:', e.message); }
let win = null, isMini = false, snapTimer = null;
const W = 680, H_HIDE = 160, H_OPEN = 475, W_MINI = 70, H_MINI = 175;
const MERGE = 22, SNAP = 80; // px merged into edge / snap distance

function workArea() {
  return screen.getDisplayNearestPoint(win.getBounds()).workArea;
}
function tellDock(side) { if (win) win.webContents.send('osokai-dock', side); }
function snapToEdge() {
  if (!isMini) return;
  const r = win.getBounds(), b = workArea();
  let x = r.x, y = r.y;
  const dL = x - b.x, dR = (b.x + b.width) - (x + r.width);
  const dT = y - b.y, dB = (b.y + b.height) - (y + r.height);
  if (Math.min(dL, dR) < SNAP) x = dL <= dR ? b.x - MERGE : b.x + b.width - r.width + MERGE;
  if (Math.min(dT, dB) < SNAP) y = dT <= dB ? b.y - MERGE : b.y + b.height - r.height + MERGE;
  if (x !== r.x || y !== r.y) win.setPosition(Math.round(x), Math.round(y));
  // report merged side(s) so the pill shape goes flush, or 'float' if free
  const sides = [];
  if (x <= b.x) sides.push('left'); else if (x + r.width >= b.x + b.width) sides.push('right');
  if (y <= b.y) sides.push('top'); else if (y + r.height >= b.y + b.height) sides.push('bottom');
  tellDock(sides.length ? sides.join(' ') : 'float');
}

function toggle() {
  if (!win) return;
  if (win.isVisible()) win.hide(); else { win.show(); win.focus(); }
}
function create() {
  win = new BrowserWindow({
    width: W, height: H_HIDE, frame: false, alwaysOnTop: true,
    skipTaskbar: true, transparent: true, resizable: false, movable: true,
    webPreferences: { preload: path.join(__dirname, 'preload.js') },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  win.hide();
  ipcMain.on('osokai-resize', (_, h) => { if (win) win.setSize(W, h === 'open' ? H_OPEN : H_HIDE); });
  // atomic setBounds: setSize+setPosition in one call (separate calls race on Win — dock failed every 2nd minimize)
  ipcMain.on('osokai-mini', () => {
    if (!win) return; isMini = true;
    const b = workArea();
    win.setBounds({ x: Math.round(b.x + b.width - W_MINI + MERGE), y: Math.round(b.y + (b.height - H_MINI) / 2), width: W_MINI, height: H_MINI });
    tellDock('right');
  });
  ipcMain.on('osokai-restore', () => {
    if (!win) return; isMini = false;
    const b = workArea();
    win.setBounds({ x: Math.round(b.x + (b.width - W) / 2), y: Math.round(b.y + (b.height - H_HIDE) / 2), width: W, height: H_HIDE });
    win.focus(); tellDock('float');
  });
  // magnetic edges: after user drags the pill, merge it into the nearest edge(s)
  win.on('move', () => { clearTimeout(snapTimer); snapTimer = setTimeout(snapToEdge, 220); });
  ipcMain.on('osokai-hide', () => { if (win) win.hide(); });
  ipcMain.on('osokai-minimize', () => { if (win) win.minimize(); });
}
app.whenReady().then(() => {
  create();
  // Primary: Alt+Space (Win) / Option+Space (Mac). Fallback Ctrl+Alt+P.
  const ok = globalShortcut.register('Alt+Space', toggle);
  if (!ok) globalShortcut.register('CommandOrControl+Alt+P', toggle);
  try {
    const tray = new Tray(path.join(__dirname, 'icon.png'));
    tray.setContextMenu(Menu.buildFromTemplate([{ label: 'Show Osok-AI (Alt+Space)', click: toggle }, { label: 'Quit', click: () => app.quit() }]));
  } catch (e) { console.log('tray icon skipped (add icon.png later):', e.message); }
});
app.on('will-quit', () => globalShortcut.unregisterAll());

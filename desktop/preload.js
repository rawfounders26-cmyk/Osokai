const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('osokai', {
  apiBase: process.env.API_BASE_URL || 'http://127.0.0.1:8765',
  resize: (mode) => ipcRenderer.send('osokai-resize', mode),
  mini: () => ipcRenderer.send('osokai-mini'),
  restore: () => ipcRenderer.send('osokai-restore'),
  onDock: (cb) => ipcRenderer.on('osokai-dock', (_, side) => cb(side)),
  hide: () => ipcRenderer.send('osokai-hide'),
  minimize: () => ipcRenderer.send('osokai-minimize'),
});

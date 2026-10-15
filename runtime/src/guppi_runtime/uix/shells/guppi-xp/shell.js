// GUPPI XP – die alte Oberfläche (Build 6, uix/retro_desktop.html) als Shell zur Wahl. Sie mountet kein Werkzeug des
// Vertrags; sie bringt den Captain auf die archivierte Seite, mit demselben Token im Fragment. Das ist bewusst keine
// Nachbildung: der alte Desktop bleibt, wie er war, und ist eine Wahl wie jede andere – nicht mehr der Weg, in den man hineinfällt.

(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;

  root.sedra.registerShell({
    id: 'guppi-xp',
    async start(ctx){
      this.ctx = ctx;
      const host = document.getElementById('sedra-root');
      host.textContent = 'GUPPI XP wird geöffnet …';
      location.replace('/retro' + location.hash);
    }
  });
})();

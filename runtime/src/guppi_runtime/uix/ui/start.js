// UI contract 1.0 – the start of the page: remember the Erscheinungsbild, boot the loader, and let nothing fail silently.
// This is the only file with top-level code besides a shell.js / tool.js (ENTWICKLUNG rule). It knows no shell and no tool.

(function(){
  const THEMES = ['klar', 'nacht'];
  const KEY = 'sedra.theme';

  function setTheme(name){
    const theme = THEMES.indexOf(name) >= 0 ? name : 'klar';
    document.documentElement.dataset.theme = theme;
    try{ localStorage.setItem(KEY, theme); }catch(_e){}      // a private window refuses: the look still works, it is just not remembered
    return theme;
  }

  function restoreTheme(){
    let stored = null;
    try{ stored = localStorage.getItem(KEY); }catch(_e){}
    if(!stored && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) stored = 'nacht';
    document.documentElement.dataset.theme = THEMES.indexOf(stored) >= 0 ? stored : 'klar';
  }

  // a problem the Captain must see, before any shell exists: plain text in the root, in his language
  function fatal(text, detail){
    const root = document.getElementById('sedra-root');
    root.replaceChildren();
    const box = document.createElement('div');
    box.className = 's-note bad';
    box.style.margin = '40px auto';
    box.style.maxWidth = '620px';
    const h = document.createElement('b'); h.textContent = text;
    const p = document.createElement('div'); p.className = 's-small'; p.textContent = detail || '';
    const hint = document.createElement('div');
    hint.className = 's-small';
    hint.textContent = 'Die alte Oberfläche (Build 6) liegt weiter unter /retro – dieselbe Runtime, dasselbe Fenster.';
    box.append(h, p, hint);
    root.append(box);
  }

  const problems = [];
  function note(where, err){
    const text = where + ': ' + (err && err.message ? err.message : err);
    problems.push(text);
    console.warn('[uix]', text);
    window.sedraBoot.problems = problems;
    if(window.sedraBoot.onProblem) window.sedraBoot.onProblem(text);     // once a shell is up it shows them in the Gespräch
  }

  window.sedraBoot = {problems, note, setTheme, restoreTheme, themes: THEMES};

  restoreTheme();
  if(window.sedraWechsel) window.sedraWechsel.restoreScale();     // B6-G-04: Schrift Normal/Groß, im Browser gemerkt
  window.addEventListener('error', e=>note('Fehler in der Oberfläche', e.error || new Error(e.message)));
  window.addEventListener('unhandledrejection', e=>{ e.preventDefault(); note('Fehler in der Oberfläche', e.reason); });

  window.sedraLoader.boot(note)
    .then(ctx=>{ window.sedraBoot.ctx = ctx; })
    .catch(err=>fatal('SEDRA konnte die Oberfläche nicht laden.', (err && err.message ? err.message : String(err))));
})();

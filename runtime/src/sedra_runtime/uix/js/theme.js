// Erscheinungsbild (UIX_STYLE_MANIFEST 8): a theme is a second token block in desktop.css, switched with html[data-theme]. Nothing else changes:
// windows, gates and texts stay the same. The choice lives in this browser (localStorage); the start menu and the Kommando switch it.
// Classic script: shares the page's global scope with the other files in uix/js; load order is set in retro_desktop.html.

const THEMES = [['retro','Retro','Das SEDRA-Deck, wie du es kennst: Himmel, Hügel, Beige'],['klar','Klar','Hell und ruhig, flache Flächen, runde Ecken'],['nacht','Nacht','Dunkel; passt zum Hardware-Fenster']];
const THEME_KEY = 'sedra.theme';

function currentTheme(){ return document.documentElement.dataset.theme || 'retro'; }

function setTheme(name){
  if(!THEMES.some(t=>t[0] === name)) throw new Error('Unbekanntes Erscheinungsbild: '+name);
  if(name === 'retro') delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = name;
  try{ if(name === 'retro') localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, name); }catch(_e){ /* private window: the theme holds until reload */ }
  renderThemePick();
}

// before the first paint, from main.js: a remembered theme comes back without a flash of the default one
function restoreTheme(){
  let name = 'retro';
  try{ name = localStorage.getItem(THEME_KEY) || 'retro'; }catch(_e){ name = 'retro'; }
  if(THEMES.some(t=>t[0] === name) && name !== 'retro') document.documentElement.dataset.theme = name;
  renderThemePick();
}

// the row of theme buttons in the start menu
function renderThemePick(){
  const box = document.getElementById('themePick');
  if(!box) return;
  box.replaceChildren(el('small','muted','Erscheinungsbild: '));
  THEMES.forEach(([id, label, hint])=>{
    const b = el('button','tool'+(currentTheme() === id ? ' on' : ''), label);
    b.title = hint; b.setAttribute('aria-pressed', currentTheme() === id ? 'true' : 'false');
    b.onclick = e=>{ e.stopPropagation(); setTheme(id); };
    box.append(b);
  });
}

// "thema nacht", "erscheinungsbild klar", "dunkel", "hell": the Kommando's way to switch
function themeCommand(text){
  const q = normalizeCommand(text);
  if(/\b(nacht|dunkel|dark)\b/.test(q)) return 'nacht';
  if(/\b(klar|hell|modern|light)\b/.test(q)) return 'klar';
  if(/\b(retro|standard|xp)\b/.test(q)) return 'retro';
  return null;
}

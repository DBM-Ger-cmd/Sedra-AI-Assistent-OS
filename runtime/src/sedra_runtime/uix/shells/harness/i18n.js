// X5: Sprache DE/EN – UI-Strings aus zentraler Textdatei (als Skript geladen), Umschaltung ohne Neustart, Fallback auf DE.
// Harness-Shell: Classic Script, globale Funktionen unter root.sedraI18n und root.t.
// Die Strings kommen von shells/harness/strings_de.js / strings_en.js (root.sedraI18nStrings),
// nicht per fetch von /uix/js/ (der Server liefert dort nur .js/.css aus, kein .json).
// Name absichtlich nicht 'sprache.js' (das ist das Mikrofon unter uix/ui/).
(function(){
  const root = typeof window !== 'undefined' ? window : globalThis;
  const KEY = 'sedra.harness.sprache';
  let cache = { de: null, en: null };
  let geladen = false;
  let code = 'de';
  let fallbackGewarnt = false;

  function gespeichert(){
    try{ const v = localStorage.getItem(KEY); return v === 'de' || v === 'en' ? v : null; }catch(_e){ return null; }
  }

  function initialisieren(){
    const gespe = gespeichert();
    if(gespe) code = gespe;
    const S = root.sedraI18nStrings || {};
    cache.de = S.de || null;
    cache.en = S.en || null;
    geladen = true;
  }

  function t(schluessel){
    if(!geladen) initialisieren();
    const tabelle = code === 'en' && cache.en ? cache.en : cache.de;
    let wert = tabelle && tabelle[schluessel] !== undefined ? tabelle[schluessel] : undefined;
    if(wert === undefined){
      wert = cache.de && cache.de[schluessel] !== undefined ? cache.de[schluessel] : schluessel;
      if(code === 'en' && !fallbackGewarnt){
        fallbackGewarnt = true;
        console.warn('Sprache: keine EN-Übersetzung für "' + schluessel + '", Fallback auf DE.');
      }
    }
    return wert;
  }

  function spracheUmschalten(neuCode){
    if(neuCode !== 'de' && neuCode !== 'en') return {ok:false, code:code};
    code = neuCode;
    try{ localStorage.setItem(KEY, code); }catch(_e){}
    return {ok:true, code:code};
  }

  function spracheAktuell(){
    return {code:code, name:code === 'en' ? 'English' : 'Deutsch', aktiv:true};
  }

  root.sedraI18n = {t: t, spracheUmschalten: spracheUmschalten, spracheAktuell: spracheAktuell, initialisieren: initialisieren};
  root.t = t;
  if(typeof module !== 'undefined' && module.exports) module.exports = {t, spracheUmschalten, spracheAktuell, initialisieren};
})();

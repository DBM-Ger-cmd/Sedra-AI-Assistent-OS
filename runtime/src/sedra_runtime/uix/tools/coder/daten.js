/* Sedra IDE: feste Beispieldateien fuer den Explorer. Keine echten Projektdaten, keine Pfade des Rechners. */
(function (root) {
  'use strict';
  const S = root.SIDE;

  const INHALT = {};
  INHALT['README.md'] = [
    '# Sedra Arbeitsbereich',
    '',
    'Dies ist ein **Beispielordner** der Sedra IDE. Alle Dateien liegen nur im Speicher der Seite.',
    '',
    '## Aufbau',
    '',
    '- `src/` Quelltext der Beispiele',
    '- `config/` Einstellungen als YAML',
    '- `docs/` Notizen und Plan',
    '- `tests/` ein kleiner Test',
    '',
    '## Bedienung',
    '',
    'Mit `Strg+Umschalt+P` oder `F1` geht die Befehlspalette auf.',
    'Mit `Strg+B` blendet die linke Seitenleiste ein und aus.',
    ''
  ].join('\n');

  INHALT['docs/plan.md'] = [
    '# Plan',
    '',
    '## Runde 1',
    '',
    '- Editor ohne Netz',
    '- Explorer mit Beispieldateien',
    '',
    '## Runde 2',
    '',
    '- Aufteilen in kleine Dateien',
    '- TODO: Pruefskript in den Testlauf aufnehmen',
    ''
  ].join('\n');

  INHALT['docs/uebersicht.md'] = [
    '# Uebersicht',
    '',
    'Die Oberflaeche hat fuenf Bereiche:',
    '',
    '1. Aktivitaetsleiste',
    '2. Seitenleiste links',
    '3. Editor mit Reitern',
    '4. Panel unten',
    '5. Chat-Leiste rechts',
    ''
  ].join('\n');

  INHALT['src/start.js'] = [
    '// Einstieg des Beispiels',
    "'use strict';",
    '',
    'const NAME = "Sedra";',
    'const AGENTEN = ["Hermes", "Pi", "Manager", "Testbot"];',
    '',
    'class Arbeitsbereich {',
    '  constructor(ordner) {',
    '    this.ordner = ordner;',
    '    this.offen = [];',
    '  }',
    '',
    '  oeffne(pfad) {',
    '    if (!this.offen.includes(pfad)) this.offen.push(pfad);',
    '    return this.offen.length;',
    '  }',
    '}',
    '',
    'function begruesse(wer) {',
    '  /* TODO: Text aus der Sprachdatei holen */',
    "  return 'Hallo ' + wer + ', hier ist ' + NAME;",
    '}',
    '',
    'function zaehle(liste) {',
    '  let summe = 0;',
    '  for (const eintrag of liste) summe += eintrag.length;',
    '  return summe;',
    '}',
    '',
    'const bereich = new Arbeitsbereich("sedra-arbeitsbereich");',
    'bereich.oeffne("README.md");',
    'console.log(begruesse(AGENTEN[0]), zaehle(AGENTEN));',
    ''
  ].join('\n');

  INHALT['src/agenten.py'] = [
    '"""Beispiel: Liste der Agenten mit Zustand."""',
    'from dataclasses import dataclass',
    '',
    '',
    '@dataclass',
    'class Agent:',
    '    name: str',
    '    zustand: str = "bereit"',
    '    auftraege: int = 0',
    '',
    '    def nimm(self, auftrag: str) -> None:',
    '        # Auftrag annehmen und zaehlen',
    '        self.zustand = "arbeitet"',
    '        self.auftraege += 1',
    '',
    '',
    'def lade_agenten() -> list:',
    '    namen = ["Hermes", "Pi", "Manager", "Testbot"]',
    '    return [Agent(name=n) for n in namen]',
    '',
    '',
    'def bericht(agenten: list) -> str:',
    '    zeilen = [f"{a.name}: {a.zustand} ({a.auftraege})" for a in agenten]',
    '    return "\\n".join(zeilen)',
    '',
    '',
    'if __name__ == "__main__":',
    '    alle = lade_agenten()',
    '    alle[0].nimm("Runde 1")',
    '    print(bericht(alle))',
    ''
  ].join('\n');

  INHALT['src/werkzeuge.py'] = [
    '"""Beispiel: kleine Helfer."""',
    '',
    '',
    'def zeilen_zaehlen(text: str) -> int:',
    '    return len(text.splitlines())',
    '',
    '',
    'def kuerze(text: str, laenge: int = 40) -> str:',
    '    if len(text) <= laenge:',
    '        return text',
    '    return text[: laenge - 3] + "..."',
    ''
  ].join('\n');

  INHALT['config/shell.yaml'] = [
    '# Beispiel einer Shell-Beschreibung',
    'name: ide',
    'titel: "Sedra IDE"',
    'sprache: de',
    'bereiche:',
    '  - explorer',
    '  - editor',
    '  - panel',
    '  - chat',
    'netz: false',
    'zeilen_grenze: 400',
    ''
  ].join('\n');

  INHALT['config/profile.yaml'] = [
    '# Beispielprofile',
    'profile:',
    '  standard:',
    '    thema: dunkel',
    '    schrift: 13',
    '  hell:',
    '    thema: hell',
    '    schrift: 13',
    ''
  ].join('\n');

  INHALT['tests/test_start.py'] = [
    'import unittest',
    '',
    'from src.werkzeuge import kuerze, zeilen_zaehlen',
    '',
    '',
    'class TestWerkzeuge(unittest.TestCase):',
    '    def test_zeilen(self):',
    '        self.assertEqual(zeilen_zaehlen("a\\nb"), 2)',
    '',
    '    def test_kuerze(self):',
    '        self.assertEqual(kuerze("abc", 10), "abc")',
    '',
    '',
    'if __name__ == "__main__":',
    '    unittest.main()',
    ''
  ].join('\n');

  S.ARBEITSBEREICH = 'sedra-arbeitsbereich';
  S.ZWEIG = 'beispiel-zweig';
  S.BAUM = [
    { name: 'config', kinder: [{ name: 'profile.yaml' }, { name: 'shell.yaml' }] },
    { name: 'docs', kinder: [{ name: 'plan.md' }, { name: 'uebersicht.md' }] },
    { name: 'src', kinder: [{ name: 'agenten.py' }, { name: 'start.js' }, { name: 'werkzeuge.py' }] },
    { name: 'tests', kinder: [{ name: 'test_start.py' }] },
    { name: 'README.md' }
  ];
  const GIT = { 'src/start.js': 'M', 'src/agenten.py': 'U', 'docs/plan.md': 'U', 'config/shell.yaml': 'M' };

  S.ZEITACHSE = [
    { text: 'Beispieldateien angelegt', zeit: '09:12' },
    { text: 'Plan um Runde 2 ergaenzt', zeit: '10:40' },
    { text: 'Agentenliste hinzugefuegt', zeit: '11:05' }
  ];

  function lege(knoten, vor) {
    knoten.forEach(function (k) {
      const p = vor ? vor + '/' + k.name : k.name;
      k.pfad = p;
      if (k.kinder) { lege(k.kinder, p); return; }
      const t = INHALT[p] || '';
      S.dateien[p] = { pfad: p, name: k.name, inhalt: t, gespeichert: t, sprache: S.sprachVon(k.name), git: GIT[p] || '' };
    });
  }
  lege(S.BAUM, '');
  S.stelleHer();
})(window);

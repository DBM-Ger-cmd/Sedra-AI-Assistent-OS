# DevVM Phase 5: Fenster und Live-Ticker, von GUPPI selbst gebaut (2026-10-06)

Freigabe des Captains: **Bau ja, Integration nein.** Alle Ergebnisse liegen als Kandidaten unter `workspace/GUPPI_OS/runtime_data/devvm_candidates/`, nichts wurde in `runtime/src` oder `uix/` übernommen.

## 1. Teil A: Datenschicht `devvm_view.py` (Python, in der DevVM gebaut, in der microVM geprüft)
Auftrag und versteckte Abnahme: `runtime/benchmarks/devvm_specs/phase5_view.py` (ein Auftrag) und `phase5_view_staged.py` (vier Stufen). Läufer: `benchmarks/devvm_build.py`.

| Weg | Ergebnis |
|---|---|
| Ein Auftrag, Eskalation (Jan allein, Qwen-Check, Qwen bei Fehlschlag) | 0 von 5 Versuchen |
| Ein Auftrag, Pipeline (Planer teilt in Schritte) | 0 von 2 (der Planer teilte nicht) |
| **Vier Stufen im selben Arbeitsbereich, je eigene Abnahme** | Versuch ohne Nacharbeit: 2 von 4 Stufen bestanden, Versuch 2 nur Stufe 1; **mit zwei Nacharbeitsrunden (Fehlerausgabe der Abnahme, nicht der Test): 4 von 4, ein Nacharbeitslauf nötig** |

Der Kandidat `phase5_view_staged/attempt_01_20261006_163531/devvm_view.py` besteht auf dem Host alle vier Abnahmetests. Seine eigenen Tests (`tests/test_devvm_view.py`) sind nicht lauffähig (0 Tests gefunden): die Vorgabe „eigene Tests“ ist nicht erfüllt.

Ursachen der Fehlschläge, alle behoben oder erkannt:
- `submit_plan` kürzte Checks still bei 2000 Zeichen (unlesbar): jetzt nie gekürzt, über 8000 Zeichen abgelehnt.
- Antwortlimit des Planers 4000 Token war zu klein: jetzt 10 000.
- Das Beispiel `pkg/mod.py` in der Werkzeugbeschreibung verleitete Jan zu `pkg/`: jetzt `mod.py` und `tests/test_mod.py`.
- Meine Aufgabe war bei `time` mehrdeutig: klargestellt.
- Dauerhaft: **die Modelle vergessen die Randfälle der Aufgabe** (Eingaben, die keine Dicts sind). Die vom Planer geschriebenen Checks prüfen sie nicht, deshalb nimmt der eigene Check falschen Code an (vier von sieben Läufen). Nur die Abnahme von außen findet sie.

## 2. Teil B: Fenster `devvm.js` (JS, in der DevVM gebaut, auf dem Host mit node geprüft)
Die DevVM-Richtlinie erlaubt seit heute `.js .css .html` (Captain: ja). Die microVM führt nur Python aus, JS wird deshalb auf dem Host mit node geprüft (`host_hidden`).
- **Stufe 1, reine Funktion `devvmViewModel`:** bestanden (Abnahme mit node), nach zwei Nacharbeitsrunden.
- **Stufe 2, Fenster (`renderDevvm`, `openDevvm`, `refreshDevvm`):** die node-Abnahme (Funktionen vorhanden, liest `/api/devvm`, prüft Fokus und `document.hidden`, nur lesend) besteht, **aber meine Prüfung im Browser findet Fehler**, die kein Test sieht:
  1. Aktiver Reiter geht beim Aktualisieren verloren (im ersten Kandidaten).
  2. Der Aktualisierungs-Timer stoppt, wenn das Fenster den Fokus verliert, und startet nicht neu (im ersten Kandidaten).
  3. Das Fenster wurde bei jedem `openDevvm()` doppelt angelegt, die Steuerknöpfe waren leer und englisch (beides in der Nacharbeit behoben).
  4. **Der letzte Kandidat hat einen Rückfall:** `refreshDevvm()` schreibt bei jedem Aufruf „Lade ...“ in das Fenster und zeichnet bei unveränderten Daten nicht neu: das Fenster bleibt leer. Zwei Nacharbeitsrunden mit Beschreibung haben das nicht behoben (die Antworten wurden bei 4000 Token abgeschnitten).
- Stand: **Kandidat nicht abnahmefähig.** Die Abnahme von GUPPI aus gesehen ist grün, die des Captains rot.

## 3. Was daraus folgt
1. **Der Weg „Jan allein, dann eskalieren“ taugt für kleine Fehlerbehebungen, nicht für große Aufgaben.** Große Aufgaben brauchen Stufen mit eigener Abnahme von außen (das ist die Phase-6-Form).
2. **Der Check des Planers ist die Schwachstelle.** Er prüft die Randfälle des Auftrags nicht. Besserung: der Planer muss je Anforderung eine Prüfung schreiben (nicht je Beispiel), und eine Abnahme von außen (Captain oder Testmodul) bleibt nötig.
3. **Browser-Prüfung für UI-Bau fehlt in der DevVM.** Ein DOM-Test (jsdom oder Browserpane) als Host-Abnahme würde den „Lade ...“-Fehler finden. Vorschlag: eine kleine Host-Abnahme mit gestützter DOM-Attrappe.
4. **Antwortlimit:** Große Dateien werden bei 4000 Token je Antwort abgeschnitten (`answer_cut` in vielen Läufen). Für Entwickler, die Dateien schreiben, ein höheres Limit (8000) prüfen.

## 4. Nicht erledigt
- Server-Route `/api/devvm` (liest `devvm_view.build_view` über die vorhandenen Arbeitsbereiche und das Audit), CSS, Menüeintrag und die Anbindung an `main.js` (Fenster-Registrierung für ziehen und skalieren): das ist Integration und wartet auf die Freigabe.
- Der Live-Ticker ist als Reiter „Live“ im selben Fenster vorgesehen; ein eigenes kleines Ticker-Fenster ist nicht gebaut.
- Das Testmodul (Entwurf in `TESTMODUL_VORBEREITUNG_2026-10-06.md`) und die Messreihe „zuverlässige Zahl von Unter-Agenten“ sind nur geplant.

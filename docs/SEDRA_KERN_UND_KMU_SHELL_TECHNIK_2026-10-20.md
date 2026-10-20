# SEDRA: Kern und Shell „KI Gateway für KMU“ – technische Übersicht

**Stand:** 20.10.2026 · **Zweck:** Zusammenfassung für das Kurs-Dashboard
**Quelle:** der Arbeitsstand im Hauptverzeichnis (Branch `release-vorbereitung`, Basis Build 25). Stand der Zahlen: heute gezählt.

## 1. Was SEDRA ist

SEDRA ist ein lokales Programm, das Arbeit mit KI-Modellen unter festen Regeln ausführt. Der Kern läuft auf dem eigenen Rechner.
Oberflächen (Shells) sitzen darauf und zeigen, was der Kern tut. Die Entscheidung, was den Rechner verlassen darf, trifft der
Kern, nicht die Oberfläche.

## 2. Der Kern

**Umfang:** 342 Python-Dateien mit rund 43.000 Zeilen, 187 Testmodule. Der Kern ist nach Aufgaben gegliedert:

| Bereich | Aufgabe |
|---|---|
| `core/` | Grundlagen, Inhaltsschutz (`content_guard`, `content_policy`) |
| `core/b6core/` | eingefrorener Schutzkern (Erkennung, Pseudonymisierung), Herkunft per Prüfsumme gesichert |
| `models/` | Modellanbindung: lokal (llama-server), Cloud nur über Freigabe |
| `gateway/` | KI Gateway: Vorgänge, Schutzklassen, Regeln, Ablage |
| `desk/` | Zustand der Oberfläche, Entscheidungen, Installation |
| `uix/` und `uix_server.py` | Oberfläche und HTTP-Schnittstelle (Token, Modul-Freigaben) |
| `sprache/` | Aufnahme und Spracherkennung (Anbieter erkennen, sonst ehrlich „kein Anbieter“) |
| `fisch/` | Übersetzen, Nachrichten, Transkripte (Shell „Translator“) |
| `jobs/`, `agent_manager/`, `capabilities/`, `tools/`, `sandbox/` | Ausführung, Werkzeuge, Prüfumgebung |

**Grundregeln des Kerns**
- Personendaten (R-01) gehen nur lokal, bis Rechtsgrundlage und Auftragsverarbeitung dokumentiert sind.
- Zugangsdaten und Kartendaten sperren den Vorgang vollständig: kein Modellaufruf, auch nicht lokal.
- Eine Freigabe gilt genau einmal, für genau diese Anfrage (Bindung aus Anfrage, Dokument, Klasse, Weg, Zweck).
- Ein Modell, das eine Freigabe umgehen will, kann es nicht: Entscheidungen erteilt nur der Kern.
- Jede Aktion landet im Audit-Protokoll (Prüfsummen und Gründe, keine Inhalte).

**Schnittstelle:** Die Oberfläche spricht nur über HTTP mit dem Kern. Jede Anfrage nennt ihren Absender. Der Server prüft,
ob dieser Absender die Route in seinem Manifest hat (`tool_route_not_allowed`). Der Zugangsschlüssel bleibt im Kern.

## 3. Die Shell „KI Gateway für KMU“ (`gateway-kmu`)

**Zweck:** Die Arbeitsfläche des KI Gateways im Design der Präsentation „KI Gateway für KMU · B6 · SEDRA“.

**Aufbau:** drei Zonen.
- **Kopf:** Marke, Titel, der Ablauf als fünf Schritte (Aufgabe eingeben → Schutz prüfen → Entwurf erzeugen → Ergebnis
  prüfen → selbst entscheiden). Der Ablauf ist Anzeige, keine Schaltfläche. Beim Rollen wird der Kopf kompakt.
- **Werkstück:** Mitte, rollt. Darin das Werkzeug `gateway` mit Vorgängen, Dateien, Regeln, Verlauf und dem Überblick.
- **Gespräch:** unten, mit dem Gesprächswerkzeug, in der Höhe verstellbar.

**Gestaltung:** Alle Farben, Schriften und Abstände kommen aus den Tokens `--kmu-…` in `ui/tokens.css`. Kein Hex-Wert in der
Shell. Die beiden Folienbilder (Bogen mit Schild, Kugel) liegen im Shell-Ordner, verkleinert.

**Dateien:**
- `shells/gateway-kmu/shell.js` (113 Zeilen), `shell.css` (217), `shell.yaml`, `README.md`
- Bilder: `kmu-hero.png`, `kmu-glow.png`, `kmu-grafik.png`
- Vollauflösung der Bilder: `runtime/assets/kmu-praesentation/`

**Werkzeug dahinter:** `gateway` (Vorgänge, Schutzklasse, Entwurf, Prüfung), eingebettet darin `schutz` (Überblick,
Regeln, Selbst ausprobieren, Verlauf). Die Shell zeigt keine Nachweis-Spalte daneben; der Überblick kommt aus dem Werkzeug.

## 4. Das KI Gateway (Ablauf eines Vorgangs)

1. **Anfrage** eingeben, optional mit einem Dokument (.md, .txt, .docx).
2. **Prüfung:** Schutzklasse SK0–SK3, Merkmale (Personenbezug, Besondere Kategorien, Zugangsdaten, Geschäftsgeheimnis,
   Gehalt, Personalnummern …), erlaubte Wege (lokal oder Cloud), Regelbuch R-01 bis R-16 mit Bezug und Begründung.
3. **Übergabe:** der Text mit Platzhaltern (`<PERSON_001>`, `<EMAIL_001>`), nur wenn erlaubt.
4. **Freigabe:** ein Klick, gebunden an genau diesen Vorgang. Bei Sperre kein Knopf.
5. **Entwurf** und **Prüfung:** der Entwurf wird als KI-Entwurf gekennzeichnet; er wird erst nach deiner Prüfung ausgegeben.
   Kein Versand, nichts verlässt den Rechner ohne Freigabe.

**Zusätzliche Erkennung** (`gateway/zusatz.py`, neben dem eingefrorenen Schutzkern): Zugangsdaten, Geschäftsinformationen,
Gehalt, Personalnummern, Anschlüsse, Geburtsdaten, Kontokennungen, Anweisungen an die KI.

## 5. Tests und Prüfung

| Prüfung | Stand |
|---|---|
| Gesamter Testsatz (187 Module) | Im letzten vollständigen Lauf: 170 grün, 0 rot. 16 Module ohne Ergebnis, weil die DevVM-Abhängigkeit `dulwich` fehlt. |
| Gateway-Module | grün (45 Tests in `test_gateway`, dazu `test_gateway_kmu_shell`, `test_gateway_menu_browser`) |
| Synthetische Prüffälle (20 Fälle, Büroalltag) | Auswertung siehe `docs/PRUEFBERICHT_KI_GATEWAY_KMU_2026-10-20.md`. Nach der letzten Änderung: keine Zugangsdaten und keine Gehaltsdaten mehr im Klartext; Namen erkannt, bis auf einen Vornamen in einer Notiz. |

**Bekannte offene Punkte (Stand heute):**
- Personalnummern, Anschlüsse und Geburtsdaten werden erkannt und lokal gehalten, aber im Text nicht ersetzt.
- Ein einzelner Vorname ohne Nachnamen (z. B. „Paula“ in einer Notiz) bleibt stehen.
- Zugangsdaten sperren den ganzen Vorgang. Das Dokument ist dann nicht auswertbar. Eine Lösung (maskiert speichern oder nur
  Fundstellen zeigen) braucht eine Entscheidung.
- Die Namenserkennung ist bewusst konservativ; Änderungen am eingefrorenen Schutzkern brauchen Freigabe.

## 6. Für das Dashboard

- **SEDRA:** „Lokaler Kern für KI-Arbeit unter festen Regeln: Personendaten bleiben lokal, Freigaben gelten genau einmal,
  jede Aktion wird protokolliert.“
- **KI Gateway für KMU:** „Eine Anfrage, ein klarer Ablauf: prüfen, freigeben, Entwurf, selbst entscheiden.“
- **Was man zeigen kann:** eine unkritische Anfrage (lokal, freigegeben), eine Kundenanfrage mit Personendaten
  (Platzhalter, nur lokal), eine gesperrte Anfrage mit Zugangsdaten.
- **Was man nicht behaupten sollte:** vollständige Erkennung aller Personen oder Datenarten, Rechtskonformität,
  Cloud-Verarbeitung ohne Freigabe, Transkription ohne installierten Anbieter.

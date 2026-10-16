# TICKET B6-G-04 – Umschalter in jeder Shell, Lesbarkeit, Korpuslauf (IMPLEMENTED/TESTED, 15.10.2026)

**Status:** Anfrage Klaus (Chat 15.10. 15:11, Q2) als Ticketfreigabe; umgesetzt und auf Linux getestet. **Nicht abgenommen.** Gate: Klaus.
**Vorher:** Build 21 (`08670f1c…9181`). **Ergebnis:** `GUPPI_Runtime_v1.20_Build_022_B6-G-03_G-04_2026-10-15.zip`, SHA-256 `cd55073a9e08b0084899c450ca945cdef666f31fae0a5a54c6e887bad6d60193`; Patch gegen den Stand nach B6-G-01: `PATCH_B6-G-03_G-04_Build022_2026-10-15.diff`, SHA-256 `44b62e8b…84a19`. Ersetzt Build 21 (ZIP und Patch).
**Doku im Prototyp:** `docs/BUILD_22_UMSCHALTER_LESBARKEIT_2026-10-15.md`, Bildschirmfotos `docs/shots/build22/`.

## (a) Was gebaut ist
| Teil | Inhalt | Dateien |
|---|---|---|
| Umschalter | runder Knopf unten rechts in **jeder** Shell (Seite, nicht Shell): Übersicht der Oberflächen (nur dieser Lauf), Wechseln zu jeder anderen (gespeichert, Seite lädt neu), Darstellung Klar/Nacht, Schrift Normal/Groß; Alt+S, Esc, Tastaturfokus; nicht in der Übersicht selbst; nur `GET /api/uix/modules`, `POST /api/uix/shell` | `uix/ui/wechsel.js`, `wechsel.css`, `desk.html`, `ui/loader.js`, `ui/start.js` |
| Lesbarkeit | Schriftstufen +1 (Grundtext 14 px), Stufe „Groß“, Zeilenabstand 1,5, Hinweistext `--muted` mit ≈ 5,6:1 Kontrast | `ui/tokens.css` |
| Werkzeug `gateway` | Beschreibungen in „small“, Felder in Grundstufe, Kästchen 16 px, Stationen deutlicher, Fakten-Raster, Tabelle, Entwurf 1,65 | `tools/gateway/tool.css` |
| Werkzeug `regelbuch` | kurzer Kopf, umbrechende Cloud-Pille, kein waagerechter Überlauf | `tools/regelbuch/tool.js`, `tool.css` |
| Korpus-Adapter | liest Korpus v0.2 (CSV + inputs/, Anhang .txt als Dokument, PDF → NOT_TESTABLE) | `benchmarks/b6_korpus_gegen_guppi.py` |
| Doku | BUILD_22, CHANGELOG, Logbuch, README, BETRIEB, BUILD.txt | docs/ |

## (b) Tests (Linux, Python 3.13)
| Was | Ergebnis |
|---|---|
| `test_uix_flows` – neu: Umschalter im Cockpit (Einträge, eigene Shell fehlt, Nacht+Groß wirken auf die Grundschrift, Esc, Alt+S, Übersicht erreicht, Schriftwahl überlebt das Neuladen, kein waagerechter Überlauf, Menü zu = unsichtbar) und in der Studio-Shell (aus Vorgabe) | 8/8, dreimal hintereinander |
| `test_uix_contract` | 30/30 |
| `uix_check` Cockpit / Minimal / Paperclip / GateWay Studio / GUPPI XP | 30/30 · 30/30 · 30/30 · 30/30 · 3/3 |
| Volle Suite | 2.129 Tests, 1 Fehler = bekannter Umgebungsfehler, 49 übersprungen |
| Korpus v0.2 gegen `b6-datenregeln-0.1` | 15 Fälle: 10 PASS, 4 FAIL, 1 NOT_TESTABLE; 3 „kritisch“ = Quellenregister-Fälle (TC-004/008/013), nicht Scanner; TC-003 = R-01 | `MESSUNG_KORPUS_v0.2_GEGEN_GUPPI_b6-datenregeln-0.1_2026-10-15.md` |
| Nicht gelaufen | Windows; echtes Modell; Sichtprüfung durch Klaus auf dem eigenen Bildschirm |

Zwei Befunde beim Bauen, beide geschlossen: das Menü war trotz `hidden` sichtbar (CSS `display:grid` schlug das Attribut – jetzt `.sx-panel[hidden]{display:none}` und ein Test, der Sichtbarkeit prüft, nicht das Attribut); das Regelbuch erzeugte in der Nachweisspalte waagerechten Überlauf (jetzt `min-width:0`, Umbruch, Test misst `scrollWidth`).

## (c) Offen
Sichtprüfung und Abnahme durch Klaus; Windows-Lauf; Korpus-Sollwert TC-003 gegen R-01 abgleichen (Torsten/Klaus); 93-Fälle-Korpus (KIMOAN-JSON) weiterhin nicht vorhanden; G-02 unverändert.

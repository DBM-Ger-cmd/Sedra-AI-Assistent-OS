# ENTWURF – Abnahmekriterien für IF-MOD-01

| Feld | Wert |
|---|---|
| Bezug | IF-MOD-01 (gestellt, Variante 1), `docs/IR_MOD-01_ENTWURF.md` (Z1, Z2, Z3) |
| Auftrag | Auftrag v7 Coder 2, Aufgabe 2, nur Text |
| Basis | `e83d0af16bb92976edede808274db62b1717f8a2` (`origin/main`) |
| Wer ändert | der **Updater** (Z1/Z2) bzw. ein Captain-Auftrag (Z3), nicht Coder 2 |
| Herkunft | `NEW_AI_GENERATED`; Fundstellen und Testnamen `EXISTING_REUSE`; Pfade relativ zu `runtime/src/sedra_runtime/` bzw. `runtime/tests/` |
| Testdateien angelegt? | **nein**. Fehlende Tests sind nur beschrieben |

## 0. Ausgangsmessung

```
cd runtime
python benchmarks/run_tests.py test_desk_kinds test_desk_gateway test_freigabe_vollstaendig test_n8n_missions
→ 65 Tests, 0 übersprungen, 0 rot  (20 + 19 + 17 + 9 Methoden)
```

Lauf auf `e83d0af` in einer isolierten Linux-Kopie, Python 3.13. Das Repo blieb unverändert.

## 1. Kriterien

Jedes Kriterium ist eine prüfbare Aussage. Unter „heute“ steht, ob das Verhalten im Code schon gilt. Coder 2 hat das am Code nachgeprüft, Befehle in §3.

### A1 – Ein neues Paket-Modul wird über `MODULES` geladen

**Aussage:** Steht ein Modul `sedra_runtime.<paket>.desk` in `desk/extensions.py:3` `MODULES` und hat es eine Funktion `register(registry, hub)`, dann sind seine Kinds nach dem Start der Oberfläche registriert, das Register ist eingefroren (`uix_server.py:159–162`), und `hub.kinds.problems` ist leer.

| | Test | Was er zeigt |
|---|---|---|
| vorhanden | `test_desk_kinds.Register.test_echo_is_reached_through_extensions_only` | `extensions.load` lädt ein Modul aus einer **übergebenen** Liste und registriert seinen Typ mit Verben |
| vorhanden | `test_n8n_missions.Missions.test_desk_registers_app_and_keeps_other_extensions` | im echten Hub: das Register ist eingefroren, der Typ `workflow` aus der **echten** `MODULES`-Liste ist da, `problems == []` |
| vorhanden | `test_desk_kinds.Register.test_freeze_ends_registration`, `test_desk_kinds.ThroughTheServer.test_the_registry_is_frozen_after_the_start` | nach dem Einfrieren kommt kein Typ dazu |
| **fehlt** | Test, der für **jeden** Eintrag in `MODULES` prüft: Modul importierbar, `register` vorhanden, mindestens ein Kind registriert, kein Eintrag in `problems` | Heute gibt es das nur für `workflow` (über `test_n8n_missions`). Eine neue Zeile in `MODULES` mit Tippfehler fiele erst im Betrieb auf (Audit `DESK_KIND_REFUSED`) |

### A2 – Ein Ladefehler eines Moduls stört die anderen Kinds nicht

**Aussage:** Scheitert ein Modul aus `MODULES` beim Import, fehlt ihm `register` oder wirft `register` eine Ausnahme, dann (a) wird seine halbe Registrierung zurückgenommen, (b) entsteht genau ein Audit `DESK_KIND_REFUSED` mit Modul und Grund, (c) werden alle übrigen Module trotzdem geladen (`desk/extensions.py:13–31`).

| | Test | Was er zeigt |
|---|---|---|
| vorhanden | `test_desk_kinds.Register.test_a_duplicate_type_is_refused_and_the_rest_keeps_running` | Fall „doppelter Typ“: halbe Registrierung zurückgenommen, Audit `DESK_KIND_REFUSED` mit `kind_already_registered`, eingebaute Typen unverändert |
| **fehlt** | Fall **Import scheitert** (`ImportError`) | heute ungetestet; Verhalten gilt (§3, Probe P2: Grund `kein Modul`, Rest geladen) |
| **fehlt** | Fall **kein `register`** (`extension_without_register`) | heute ungetestet; Verhalten gilt (P2) |
| **fehlt** | Fall **`register` wirft nach einer Teilregistrierung** (beliebige Ausnahme) | heute ungetestet; Verhalten gilt (P2: Teilregistrierung zurückgenommen) |
| **fehlt** | **Reihenfolge:** ein fehlerhaftes Modul **vor** einem gültigen in derselben Liste; das gültige wird trotzdem geladen | der vorhandene Test lädt nur ein Modul; P2 zeigt es mit vier Modulen |

### A3 – Typnamen mit `_` oder `-` werden abgelehnt, wo die Regel es verbietet

**Regeln im Code:**
- Kind-Name: `[a-z][a-z0-9_]{1,31}` (`desk/kinds.py:52`) → **Bindestrich verboten**, Unterstrich erlaubt, Großbuchstaben verboten, mindestens 2 Zeichen.
- `handles` im Manifest: `^[a-z0-9-]{2,40}(:(\*|[a-z0-9-]{1,40}))?$` (`desk/gateway.py:32`) → **Unterstrich verboten**, Bindestrich erlaubt.
- Folge (IF-MOD-01, Namensregel): Ein Typ, den eine App öffnen soll, muss **beide** Regeln erfüllen, darf also weder `_` noch `-` enthalten.

**Aussagen:** (a) `register(Kind('factory-run', …))` → `ValueError('kind_name_invalid')`. (b) Ein Manifest mit `handles: ['factory_run']` → Fehler `handles_unknown_type`. (c) `factory` wird an beiden Stellen angenommen. (d) Ein Paket-Werkzeug (`trust: CORE`) mit einem Typ außerhalb von `OBJECT_TYPES` → `handles_unknown_type` (`desk/gateway.py:164`).

| | Test | Was er zeigt |
|---|---|---|
| vorhanden | `test_desk_gateway.ManifestRules.test_handles_may_carry_a_suffix_like_the_schema` | falsche Formen (`issue:`, `issue:**`, `Issue:alle`, `issue:a:b`, `:alle`) abgewiesen; Server und `tool.schema.json` nutzen dasselbe Muster |
| vorhanden | `test_desk_gateway.ManifestRules.test_an_own_tool_may_bring_its_own_object_type_but_a_core_tool_may_not` | Aussage (d) |
| vorhanden | `test_desk_gateway.ManifestRules.test_every_rule_of_the_contract_is_enforced` (Fall `handles_unknown_type: {"handles": ["Space Ship!"]}`) | Leerzeichen und Großschreibung abgewiesen |
| **fehlt** | Aussage (a): Kind-Name mit **Bindestrich**, Großbuchstaben oder nur 1 Zeichen → `kind_name_invalid` | `kind_name_invalid` kommt in keinem Test vor; Verhalten gilt (P1) |
| **fehlt** | Aussage (b): `handles` mit **Unterstrich** abgewiesen | die Liste der falschen Formen enthält keinen Unterstrich; Verhalten gilt (P1) |
| **fehlt** | Aussage (c) als Gegenprobe: derselbe Name besteht **beide** Prüfungen | nur so ist die Namensregel aus IF-MOD-01 belegt |

### A4 – Jede neue Antragsart braucht einen Eintrag in `ARTEN`

**Aussage:** Jede Art, die über `desk/gated.py` `register_applier` angemeldet oder vom Server über `_remember` angelegt wird, steht als `request:<art>` in `desk/freigabeklasse.py:20` `ARTEN`. Fehlt sie, ist `test_freigabe_vollstaendig` rot.

| | Test | Was er zeigt |
|---|---|---|
| vorhanden | `test_freigabe_vollstaendig.Entscheidungsarten.test_antragsarten` | alle Arten aus `desk/decisions.py` `REQUEST_TITLE` und `APPLY` stehen in `ARTEN` |
| vorhanden | `test_freigabe_vollstaendig.Entscheidungsarten.test_antragsarten_aus_dem_code` | Arten aus `_remember('…')` in `uix_server.py` und aus `register_applier(…)` in **drei festen Dateien** (`desk/orchestra_kinds.py`, `wissen/desk_wissen.py`, `harness/antraege.py`) stehen in `ARTEN`. Dass er greift, ist belegt: auf `20ef720` war er rot, weil `request:harness_prozess` fehlte (`docs/BESTAND_MOD_01_APPS.md` §4) |
| **Lücke im Test** | Die Dateiliste ist **fest**. Ein neues Modul, z. B. `factory/desk.py`, das `register_applier` ruft, wird **nicht** durchsucht. Eine neue Factory-Antragsart ohne `ARTEN`-Eintrag bliebe grün. `register_applier` legt die Art nur zur Laufzeit in `_APPLIERS` ab (`desk/gated.py:35–43`), und kein Test vergleicht `_APPLIERS` mit `ARTEN` | Heute vollständig, weil alle 9 Aufrufe von `register_applier` in genau diesen drei Dateien liegen (§3, P3) |
| **fehlt** | Variante a: Der Test durchsucht **alle** `*.py` unter `sedra_runtime/` nach `register_applier(`, nicht eine feste Liste | Änderung an `tests/test_freigabe_vollstaendig.py` → Owner Updater/Captain (Freigabe-Test) |
| **fehlt** | Variante b: Nach dem Laden aller `MODULES` ist jede Art in `gated._APPLIERS` als `request:<art>` in `ARTEN` | Laufzeitprobe, unabhängig von Dateinamen; ergänzt Variante a |
| hinweis | `gated.request` kann die Art auch als Text übergeben, z. B. `wissen/desk_basis.py:151` mit `"wissen_quelle"`. Heute ist das abgedeckt, weil dieselbe Art als `KIND_QUELLE` (`wissen/desk_wissen.py:20`) mit `register_applier` angemeldet ist. Eine neue Art, die nur als Text in `gated.request` steht, fände keiner der beiden Wege | Variante a sollte auch Text-Arten in `gated.request(hub, '<art>', …)` durchsuchen |

## 2. Abnahme von IF-MOD-01 als Ganzes (Vorschlag)

IF-MOD-01 gilt als umgesetzt, wenn:

1. die Reservierungsregel für Z1/Z2 (eine Zeile je Auftrag, Updater führt zusammen) im Register oder in `04_REGISTER/DATEI_RESERVIERUNG.md` steht;
2. die Tests zu A1 bis A4 vorhanden und grün sind, einschließlich der **fehlenden** Fälle oben;
3. `python benchmarks/run_tests.py desk test_freigabe_vollstaendig workflow` auf dem Integrationsstand grün ist;
4. Z3 unberührt bleibt, bis ein eigener Captain-Auftrag die Factory-Antragsarten nennt.

Zuständig für das Schreiben der Tests: Updater (geteilte Dateien `tests/test_desk_kinds.py`, `tests/test_desk_gateway.py`, `tests/test_freigabe_vollstaendig.py`). Coder 2 liefert auf Wunsch den Testtext als Entwurf, legt aber keine Datei an.

## 3. Proben am Code (nur lesen, Temp-Ordner, nicht eingecheckt)

**P1 – Namensregeln** (`desk/kinds.py:52`, `desk/gateway.py:32`):

| Name | als Kind | als `handles` |
|---|---|---|
| `factory` | angenommen | angenommen |
| `factory_run` | angenommen | **abgelehnt** |
| `factory-run` | **`kind_name_invalid`** | angenommen |
| `Factory` | `kind_name_invalid` | abgelehnt |
| `f` | `kind_name_invalid` | abgelehnt |

**P2 – Ladefehler** (`extensions.load` mit vier Modulen, gültiges zuletzt):

| Modul | Fehler | Audit-Grund | Folge |
|---|---|---|---|
| `kaputt` | `ImportError` | `kein Modul` | übersprungen |
| `ohne` | kein `register` | `extension_without_register` | übersprungen |
| `wirft` | registriert `halb`, wirft dann | `boom` | `halb` zurückgenommen |
| `sedra_runtime.workflows.desk` | – | – | geladen, `workflow` registriert |

**P3 – Aufrufer von `register_applier`** auf `e83d0af`: `desk/orchestra_kinds.py:904–905`, `wissen/desk_wissen.py:462–463`, `harness/antraege.py:324–328`, alle in der festen Liste des Tests.

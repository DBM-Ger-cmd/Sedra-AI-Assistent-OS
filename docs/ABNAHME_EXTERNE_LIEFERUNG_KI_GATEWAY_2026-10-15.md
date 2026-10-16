# Abnahme der ersten externen Lieferung: KI GateWay 0.3.0 (15.10.2026)

Ein anderer Chat hat aus einem früheren Projekt ein Modul für SEDRA gebaut – als Test des Einbauwegs. Hier steht, was die
Lieferung ist, was der Weg mit ihr gemacht hat, was dabei am Vertrag aufgefallen ist, und was noch fehlt. **Nichts an der
Lieferung wurde verändert.**

## 1. Was geliefert wurde

Kein Shell, sondern **zwei Werkzeuge und ein Backend**:

| Teil | Was es ist | Einbauweg |
|---|---|---|
| `uix/tools/gateway/` | Werkzeug „KI GateWay“: Vorgänge prüfen, Vorgaben, Freigabe (Slot `inhalt`, Objekttyp `gateway`) | **das Gate** – wie vorgesehen |
| `uix/tools/schutz/` | Werkzeug „KI GateWay · Schutz“: Nachweis daneben (Slot `nachweis`, Typen `gateway`, `guard`) | **das Gate** |
| `sedra_gateway/` | Python-Paket (12 Module + `b6core`, 88 Tests): Einlesen, Prüfen, KI-Triage, Pseudonymisierung, ModelGuard, Andockstelle | **keiner** – das Gate baut Oberfläche ein, keinen Code in die Runtime |
| `vorfuehrung/` | eigener Server mit Attrappe (KI) und Simulation (Cloud) | läuft für sich; nicht Teil von SEDRA |

## 2. Was der Weg mit den Werkzeugen gemacht hat – unverändert, Schritt für Schritt

1. **Durchsicht**: nichts gefunden – kein `eval`, kein eigenes `fetch`, kein Speicher, keine fremde Adresse. Beide sauber.
2. **Manifestprüfung: abgewiesen** – `handles_unknown_type`. `gateway` und `guard` sind keine Objekttypen des Vertrags.
   → **Vertragsbefund V1** (unten), geschlossen. Danach:
3. **Gate**: *„Modul ‚KI GateWay‘ (gateway) einbauen · 4 Datei(en) · als COMMUNITY, nur Leserouten (3) · Die Durchsicht hat
   nichts gefunden · bringt eigene Objekttypen: gateway“*. Freigegeben, eingebaut, Audit `UIX_MODULE_INSTALLED`.
4. **Im Cockpit**: beide erscheinen (25 Werkzeuge), „KI GateWay“ öffnet als Reiter, `uix_check --tool gateway` sagt `ok`
   (Container gefüllt, eine Handlung, Allowlist greift). Was es zeigt: **„Das KI GateWay antwortet nicht: Diesen Weg gibt es
   nicht: /api/gateway/vorgaben“** – ehrlich und richtig, denn das Backend ist nicht da.

## 3. Was am Vertrag aufgefallen ist (und geschlossen wurde)

| Nr. | Befund | Geschlossen durch |
|---|---|---|
| **V1** | **Ein fremdes Werkzeug konnte keinen eigenen Objekttyp mitbringen.** `OBJECT_TYPES` war für alle verbindlich – damit wäre jedes Werkzeug, das etwas Neues zeigt, am Manifest gescheitert. | Eigene Typen sind erlaubt für Werkzeuge, die nicht `CORE` sind und nicht aus dem Paket kommen (`own_types` im Manifest). Die Shells öffnen jeden Typ über die Registrierung; Baum und Palette kennen ihn nicht – das sagt das Werkzeug „Module“ dazu. Im Paket selbst gibt es keine Privatsprache. Tests in `test_desk_gateway`. |
| **V2** | **Das Vertrauen kam aus der Datei des Fremden.** Die Lieferung sagte `trust: CAPTAIN` – damit hätte sie durch das Gate ihre vier `POST`-Routen behalten (prüfen, freigeben, antworten, Vorgaben schreiben). | Was durch das Gate kommt, **ist COMMUNITY**, egal was das Manifest behauptet: nur Leserouten, die eingebaute `tool.yaml` sagt es, die Quelle bleibt unverändert, das Gate sagt es vorher. Hochstufen tut der Captain bewusst in der Datei. Test in `test_desk_install`. Das ist zugleich **H15** der Härtung. |
| V3 | `uix_check` kannte das Objekt eines fremden Werkzeugs nicht (OBJECTS ist eine Liste von Hand). | Ein Werkzeug mit eigenem Typ wird mit seiner Sammlung geprüft (`handles[0]`, `alle`). `start_server(prepare=…)` kann vorher einbauen. |

## 4. Was fehlt, damit das GateWay wirklich arbeitet

Die Werkzeuge sind drin; **das Backend nicht**. Das ist kein Mangel des Gates – es baut Oberfläche ein, bewusst keinen Code in
die Runtime. Für den Rest gibt es zwei Wege, und der Captain entscheidet:

| | Weg | Was es heißt |
|---|---|---|
| **A** | **Einbau durch uns**, nach §6 der Spec des anderen Chats (E6–E10): `sedra_gateway` ins Paket, Routen `/api/gateway/*` und `/api/guard/*` im Vermittler, Vorgänge unter `local_config/gateway/`, die Freigabe eines Vorgangs als Entscheidung `kind: gateway_release` in `desk/decisions.py`. | Eine Runtime-Änderung mit Prüfung: `guard.py` ist ein **zweiter ModelGuard** mit eigener Policy und eigenem Logbuch – er muss durch SEDRAs Guard (Grenzen aus Build 9, Audit-Kette), nicht daneben. Das B6-Kernmodul kommt als Fremdcode mit (`B6CORE_HERKUNFT.sha256` liegt bei). Aufwand: ein Build, mit eigener Spec vorher. |
| **B** | **Vorführung getrennt lassen**: das GateWay läuft als eigener Prozess (`vorfuehrung/server.py`), SEDRA zeigt nur die Werkzeuge. | Dann brauchen die Werkzeuge einen Weg zu dem anderen Prozess – den gibt der Vertrag heute nicht her (nur `ctx.api` an SEDRAs Vermittler). Ehrlich: Weg B ist eine Brücke, die noch niemand gebaut hat. |

Und unabhängig vom Weg: **als COMMUNITY kann das Werkzeug nichts schreiben** – kein Vorgang prüfen, keine Freigabe.
**Entscheidung des Captains (02:12): das Werkzeug Module bekommt das Verb „Schreibrouten freigeben …“ mit Gate. Gebaut:**
`POST /api/uix/trust` legt vor, das Gate nennt **genau die POST-Routen aus dem Manifest** als Risiken, erst `freigeben und
anwenden` setzt das Vertrauen auf `CAPTAIN` – und nur, wenn das Manifest noch dasselbe ist wie im Gate (`manifest_changed_since_the_request`).
Audit `UIX_MODULE_WRITE_ROUTES_GRANTED`. Mit der echten Lieferung durchgespielt: vorher 403 auf `/api/gateway/pruefen`, Gate mit
vier Routen, danach erlaubt – und `/api/mission/run` bleibt verboten. Zwei Tests in `test_desk_install`.

**Zweck, den der Captain genannt hat:** dieses Modul soll eine sichere Methode für Einzelpersonen und Firmen werden, ihre Daten
**lokal** zu prüfen, bevor sie zu Claude gehen. Das entscheidet Weg A gegen Weg B: die Prüfung muss dort sitzen, wo SEDRA ohnehin
jede Grenze bewacht – im Guard, mit der einen Audit-Kette, der Netz- und der Kostengrenze. Ein zweiter Guard daneben wäre genau
die Stelle, an der „sicher“ nur ein Wort bliebe. Der Einbau nach Weg A ist der nächste Build, mit Spec vorher.

## 5. Urteil über den Einbauweg

Der Weg hat getan, was er soll: eine Lieferung von außen ist **ohne Vorab-Korrektur** durchgelaufen, hat zwei Löcher im Vertrag
sichtbar gemacht – beide genau an der Stelle, wo „fremd“ etwas anderes heißt als „eigen“ –, und steht jetzt ehrlich im Cockpit mit
dem Satz, was fehlt. Die Lieferung selbst ist handwerklich sauber: Durchsicht ohne Fund, Vertrag eingehalten, Tests mitgebracht.

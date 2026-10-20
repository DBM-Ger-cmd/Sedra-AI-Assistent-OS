# Review-Vorlage für einen SEDRA-Kandidaten

Vorlage (V3, Captain 20.10.2026). Sie wird für jeden Kandidaten aus `runtime_data/devvm_candidates/<spec>/attempt_…/` ausgefüllt, bevor der Captain über die Übernahme (Gate G4) entscheidet.
Der versteckte Test prüft nur Verhalten; diese Liste fängt, was er nicht sieht. Jeder Punkt: ja / nein / entfällt, bei „nein“ mit Datei und Zeile.

Kopf
- Spec: `<name>`; Kandidat: `<attempt>`; Prüfer: `<wer>`; Datum: `<TT.MM.JJJJ>`
- Stempel der Spec (`spec_check --vm`): `<Datum, Python-Version>`; Bau-Zeile im Logbuch (Art BAU): `<Zeit>`

Checkliste
1. **Schnittstelle wie die Spec:** Namen, Parameter, Rückgabewerte und Ausnahmen entsprechen der Aufgabe und der Referenz; keine zusätzlichen öffentlichen Namen, die niemand verlangt hat.
2. **Fehlerfälle:** leere und falsche Eingaben, Grenzwerte, unbekannte Schlüssel; die Fehlerart ist die verlangte (keine verschluckten Ausnahmen, kein nacktes `except`).
3. **Keine Importe nach außen:** nur Standardbibliothek und die in der Spec erlaubten Module; kein Import aus `core/`, Guard oder Laufzeit-Paketen, außer die Spec verlangt es.
4. **Keine Netz- und Dateizugriffe** (auch kein `subprocess`, `os.system`, `eval`, `exec`), außer die Spec erlaubt sie ausdrücklich; erlaubte Zugriffe liegen nur im vorgesehenen Ordner.
5. **Tests grün in der VM:** versteckte Tests aller Stufen bestanden (Zeile `hidden test PASSED`), eigene Tests des Kandidaten (falls vorhanden) grün; der Lauf war in der microVM, nicht auf dem Host.
6. **Stil:** Zeilen höchstens 400 je Datei; keine Kommentare und Docstrings, die nur wiederholen, was der Code sagt; keine doppelten oder kopierten Blöcke; keine toten Hilfsdateien; Namen wie im umgebenden Code.
7. **Zeilen-Quote (L4):** Zeilen SEDRA (Kandidat) `<n>` gegen Zeilen Claude (Spec + Referenz) `<m>`; Quote Claude/SEDRA `<m/n>` (steht auch in der BAU-Zeile). Ist Spec + Tests + Referenz größer als der Code selbst, merken: beim nächsten Mal baut Claude solche Teile direkt als Harness (Regel V4).
8. **Eingriffe:** Wurde von Hand etwas geändert? Jede Handänderung mit Grund ins Logbuch (Art AENDERUNG) und in der Quote als Claude-Zeilen zählen.

Mängelliste
- `<Datei:Zeile>`: Mangel, genaue Ersetzung. (Genaue Zeilen und Ersetzungen, damit eine Nacharbeit mit `--review <datei> --seed <attempt>` sie nicht übergeht.)

Empfehlung G4: **ja / nein**
- Begründung in zwei bis drei Sätzen (was trägt die Empfehlung, was bleibt offen, ob Nacharbeit oder Handkorrektur nötig ist).
- Bei „ja“: Übernahme per `adopt_plan` oder Handkopie, relative Importe anpassen, Tests in `runtime/tests/`, Logbuch (INTEGRATION).

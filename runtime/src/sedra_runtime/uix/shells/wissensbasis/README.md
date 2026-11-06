# Wissensbasis (Shell aus Vorgabe)

Die zentrale Wissensbasis als eigene Oberfläche (Captain 26.10.2026, SPEC_SHELL_WISSEN_v1, W-E1 bis W-E5). Kein Shell-Code: `ui/frame.js`
baut sie aus `shell.vorgabe.yaml`.

```
┌─ Leiste: Wissen (hybrid · 85 % · 2 Vorschläge) · Zustand · Modell · Entscheidungen ──────────────────┐
├─ Orte ──────────┬─ Werkstück: Wissen ───────────────────────────┬─ Nachweis: Fundstelle ─────────────┤
│ Suche           │ [ Frage an das Wissen … ]                      │ docs/SPEC7… › D7.4 Suche            │
│ Quellen         │ ▌D7.4 Suche (docs/SPEC7…)        ████▌         │ davor · Treffer · danach            │
│ Vorschläge  ⚠2  │ ▌Logbuch 21.10. Werkbank Bau     ███           │ [Ins Gespräch] [Quelle zeigen]      │
│ Eigenes Wissen  │                                                 │                                     │
├─ Gespräch: „Frag das Wissen“ – Antworten mit Fundstellen [W…] ───────────────────────────────────────┤
```

- **Start:** Wissen › Suche (`start.view`), es sei denn, aus einer anderen Shell kommt ein offenes Objekt mit (Arbeitsstand, Vertrag 1.1 §10).
- **Orte:** die Ansichten des Wissens (Ortskunde `ui/places.js`: `wissen-suche` …), Bibliothek, Logbuch, Entscheidungen.
- **Nachweis:** das Werkzeug `fundstelle` – der Treffer im Zusammenhang.
- **Gespräch:** `gespraech.wissen: true` – das Gespräch fragt zuerst den Speicher; mit Modell antwortet es aus den Fundstellen und
  nennt sie `[W…]`, ohne Modell steht die Trefferliste da. Mit Personenbezug in den Fundstellen ist der Cloud-Weg für diese Frage aus.

## Abnahme
`python benchmarks/uix_check.py --shell wissensbasis` (W1, W8 mit Browser). Bildschirmfoto `preview.png` – auf dem PC erneuern.

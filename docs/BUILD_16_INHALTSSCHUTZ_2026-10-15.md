# Build 16: Der Inhaltsschutz im Kern (15.10.2026)

**Captain, 02:20:** *„Der sichere Weg zuerst.“* Build 16 setzt S1–S5 aus `SPEC_EIN_SICHERER_WEG_v1.md` um: seit diesem Build geht
**kein Modellaufruf mehr ungeprüft** an ein Modell. Das ist eine Kernänderung an SEDRA – nicht ein Modul mehr, sondern ein Schutz
an der einen Stelle, durch die alles läuft.

## 1. Was jetzt gilt – in fünf Sätzen

| | Zusage | Wo |
|---|---|---|
| **S1** | Der Inhaltsschutz ist Teil des Kerns: Scan (B6-Regeln: Schlüssel, Karten, Passwörter, Anweisungen an die KI, unsichtbare Zeichen, Personenbezug), Bewertung (ALLOW · REVIEW · PSEUDONYMIZE · BLOCK), Pseudonymisierung für die Cloud, Prüfung der **Antwort**. | `core/content_policy.py`, `core/content_guard.py`, `core/b6core/` |
| **S2** | `ModelRouter.chat` ruft ihn bei jedem Aufruf. Der Guard bekommt `complete` vom Router mit – er hat keinen eigenen Weg zum Modell und weicht auf kein anderes aus. Auch Werkzeugaufrufe einer Antwort werden geprüft (als JSON). | `models/router.py` |
| **S3** | Eine `REVIEW` ist eine SEDRA-Entscheidung in der einen Liste: *einmal* · *ablehnen*. „Einmal“ gilt für genau diesen Aufruf (Hash über alle Teile), zehn Minuten, einmal. Derselbe Aufruf ist eine Entscheidung, nicht zehn. | `desk/decisions.py` (`content_decision`), `uix_server.decide` |
| **S4** | Sein Logbuch ist die Audit-Kette: `SG_MODEL_CALL`, `SG_OUTPUT_OK`, `SG_BLOCKED`, `SG_DECISION_PENDING`, `SG_ONCE_GRANTED/USED`, `SG_DECISION_REJECTED`, `SG_STOPPED`, `SG_MODE_SET` – Hashes, Regeln, Zählungen, **nie Text**. Schreibt die Kette nicht, geht nichts hinaus. | `core/audit.py` (unverändert) |
| **S5** | Der Modus des Projekts ist die Schärfe: **Sandbox** = alle Gruppen scharf; **Beobachten** und **Vertraut** = beobachten (durchlassen, zählen, zeigen). Nichts bestätigt = beobachten. **Immer scharf**, in jedem Modus: was den Rechner verlässt (Cloud) und der Grundschutz (Form des Aufrufs, Prüffehler, Logbuch). Es gibt keinen zweiten Schalter. | `uix_server.sync_guard_mode` nach `boundaries_apply` |

## 2. Der Weg eines Aufrufs

```
Rufer ──► ModelRouter.chat ──► ContentGuard.call
                                  1 Form prüfen, jeden Teil scannen        Fehler → BLOCKED
                                  2 bewerten; Modus → scharf / beobachtet
                                      BLOCK      → ContentGuardStop(BLOCKED), Adapter nie gerufen
                                      REVIEW     → Entscheidung im Desk, ContentGuardStop(NEEDS_DECISION)
                                                   (nach „einmal“: genau dieser Aufruf läuft, einmal)
                                  3 Audit SG_MODEL_CALL                     schreibt nicht → ERROR, kein Aufruf
                                  4 fremde Teile als Daten markieren (scharf); Cloud: pseudonymisieren, erneut prüfen
                                  5 complete(prepared) → Adapter.chat        Fehler → unverändert nach oben, kein Ausweichen
                                  6 Antwort scannen: Schlüssel/Karte/Steuerzeichen → WITHHELD (scharf) / beobachtet
                                    Cloud: Platzhalter prüfen, zurückübersetzen
                                  7 Audit SG_OUTPUT_OK  → GuardResult(OK, text, binding, observed)
```

Wer die Teile eines Aufrufs einstuft: der Rufer über `trust` je Teil (`system`, `captain`, `project`, `untrusted`); sagt er nichts,
gilt die Rolle (user = captain, assistant = project, tool = untrusted). Fehlt beides, ist der Teil fremd.

## 3. Was der Captain sieht

- **Entscheidungen**: „Modellaufruf prüfen: Fremder Inhalt versucht, dem Modell Anweisungen zu geben.“ – mit Zahl der Teile, wo
  der Fund liegt (`untrusted`), Modell und Weg; die Bindung ist ein Hash. Kein Wort aus dem Aufruf. Die Karte ist dieselbe wie bei
  jeder anderen Entscheidung (das Werkzeug kennt keinen Sonderfall).
- **`GET /api/guard/status`**: Gruppen und ihre Schärfe, Zählungen (geprüft, frei, für dich, angehalten, lokal, Cloud, mit
  Platzhaltern, zurückgehalten, beobachtet), die letzten dreißig Ereignisse als Sätze, was wartet – und der Satz zur Grenze:
  *Pseudonymisierung ist keine Anonymisierung; was mit welcher Rechtsgrundlage an einen Anbieter darf, entscheidet ihr.*
  Die Antwort trägt **beide Formen**: SEDRAs (`groups`, `counts`, `recent`) und die, die das gelieferte Werkzeug `schutz` liest
  (`count`, `rules`, `events`, `pending`) – damit es ohne Änderung den Zustand von **ganz SEDRA** zeigt, nicht nur des GateWays.
  Was es nicht mehr kann: Gruppen einzeln schalten (`/api/guard/group` gibt es nicht) – die Schärfe kommt aus dem Modus.

## 4. Was bewusst noch nicht da ist

- **Keine Cloud.** `cloud_enabled` ist `False`; ein Aufruf mit `route='cloud'` endet mit `SG_CLOUD_DISABLED`. Der simulierte
  Cloud-Adapter hinter der Netzgrenze ist Build 18 (S6).
- **Keine Kostenzählung der Hilfsaufrufe** (S7, Build 18).
- **Das GateWay-Paket** (Vorgänge, Triage, Freigabe) ist Build 17 (G1–G5). `sedra_gateway/guard.py` entfällt dann zugunsten von S1.
- **Der Scanner kennt nicht jedes Schlüsselformat** (ein `sk-ant-…`-Token etwa fällt heute nur unter die weichen Regeln, wenn ein
  Wort wie „Token“ danebensteht). Das ist eine Lücke des B6-Regelwerks, nicht des Guards – sie gehört in `b6core/privacy.py`, mit
  neuer Herkunftsprüfung, nicht in eine Sonderregel daneben.

## 5. Abnahme

| Was | Ergebnis |
|---|---|
| `tests/test_content_guard.py` – ein Test je Zusage: S1 (8), S2 (6), S3 (6), S4 (2), S5 (5) | 27/27 |
| b6core: sieben Dateien, Hash für Hash gegen `HERKUNFT.sha256`; kein `urllib`/`socket`/`subprocess` | geprüft im Test |
| Live über HTTP (`benchmarks/uix_check.start_server`): Status · Aufruf mit fremder Anweisung → Entscheidung in Liste und Strip · *einmal* → genau ein Aufruf · Ereignisse ohne Text | ok |
| Volle Suite | siehe CHANGELOG |
| Vier Shells (`uix_check --shell …`) | unverändert, siehe CHANGELOG |

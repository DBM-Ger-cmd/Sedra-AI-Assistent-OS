# B6-Korpus gegen GUPPI-Matrix b6-datenregeln-0.1 – Messung 2026-10-15T15:12+02:00

Quelle: `/tmp/claude-0/-home-claude/e5674a8b-e4f0-583d-9174-427076f55ae6/scratchpad/korpus/B6_Korpus_v0.2/03_Testfaelle_v0.2-DRAFT.csv` · Fälle: 15 · **10 PASS / 4 FAIL / 1 NOT_TESTABLE** · kritische Falschfreigaben: **3**

Nur Messung (Ticket B6-G-01, G-06). Quellenklasse, Rollen und Zweck werden von der GUPPI-Matrix nicht gewertet; ein PASS ist Übereinstimmung mit dem Korpus-Soll, keine fachliche Bestätigung des Solls.

## Einordnung (Q3, nach dem Lauf)
- **Korpus:** `B6_Korpus_v0.2-DRAFT.zip` (Torsten, 15 Fälle B6-TC-001…015, Status DRAFT), hochgeladen von Klaus 15.10. 15:11; nicht der 93-Fälle-Runner-Korpus (KIMOAN-JSON fehlt weiterhin).
- **Was die Matrix nicht kennt:** Quellenregister, Quellenklassen, Gültigkeit, Versionskonflikte, Rollen. Die drei als „kritisch“ markierten Abweichungen beruhen genau darauf: TC-004 (Kundennummer allein = Grenzfall nach K-05, Review durch Quellenlage), TC-008 (Versionskonflikt zweier Quellen), TC-013 (Quelle ohne Registereintrag). Das sind **Lücken des Prototyps gegenüber dem B6-Kern** (Option C schließt sie), keine Falschfreigaben des Scanners.
- **TC-003:** Soll „Cloud nach Pseudonymisierung“, Ist „nur lokal“ – das ist **Regel R-01 des Regelwerks v0.1** (Klaus 14:08): ohne Rechtsgrundlage und AVV kein Cloudweg für Personenbezug. Der Korpus-Sollwert stammt vom 12.10. und ist mit dem Regelwerk abzugleichen (Torsten/Klaus).
- **TC-012:** PDF-Anhang, im Prototyp MVP 1 nicht lesbar → NOT_TESTABLE (B6 erwartet BLOCKED `EXTRACTION_FAILED`; im Prototyp wird die Datei abgewiesen, was dem gleichen fail-closed-Ergebnis entspricht, aber ohne Vorgang).
- **Bestanden:** beide Hard Blocks (TC-009 Injection im Anhang, TC-010 Secrets), alle LOCAL_ONLY-Fälle mit Personenbezug, die Cloud-Freigabe ohne Merkmale (TC-001).
- Kein Modellaufruf; nur Einstufung. Soll-Inhalte der Entwürfe (Preise, Zusagen) wurden nicht geprüft – dafür braucht es Station 04 mit Modell und den Output-Check des B6-Kerns.

| Fall | Quelle | Wunsch | Soll Status | Ist Status | Soll Weg | Ist Weg | Soll Merkmale | Ist Merkmale | Ergebnis | Grund |
|---|---|---|---|---|---|---|---|---|---|---|
| B6-TC-001 | Manuelle Eingabe; Q-001 FAQ v1.0 (freigegeben, gültig, öffen | CLOUD_ALLOWED | AUTO_APPROVED | AUTO_APPROVED | CLOUD_ALLOWED | CLOUD_ALLOWED | – | – | PASS | – |
| B6-TC-002 | Manuelle Eingabe; Q-002 Konditionen v1.1 (freigegeben, gülti | LOCAL_ONLY | AUTO_APPROVED | AUTO_APPROVED | LOCAL_ONLY | LOCAL_ONLY | – | – | PASS | – |
| B6-TC-003 | Manuelle Eingabe; Q-001 FAQ v1.0 (freigegeben, gültig, öffen | CLOUD_ALLOWED | AUTO_APPROVED | AUTO_APPROVED | CLOUD_AFTER_PSEUDONYMIZATION | – | – | P01 | FAIL | Weg: Soll CLOUD_AFTER_PSEUDONYMIZATION, Ist None (erlaubt: LOCAL_ONLY) |
| B6-TC-004 | Manuelle Eingabe; Q-005 Bestandsauszug 2026-10-12 (freigegeb | LOCAL_ONLY | HUMAN_REVIEW_REQUIRED | AUTO_APPROVED | – | LOCAL_ONLY | – | P01 | FAIL **kritisch** | Status: Soll HUMAN_REVIEW_REQUIRED, Ist AUTO_APPROVED |
| B6-TC-005 | Manuelle Eingabe; Q-002 Konditionen v1.1 (freigegeben, gülti | LOCAL_ONLY | AUTO_APPROVED | AUTO_APPROVED | LOCAL_ONLY | LOCAL_ONLY | – | P01 | PASS | – |
| B6-TC-006 | Manuelle Eingabe; Q-007 Angebots-Checkliste v1.0 (freigegebe | LOCAL_ONLY | AUTO_APPROVED | AUTO_APPROVED | LOCAL_ONLY | LOCAL_ONLY | – | – | PASS | – |
| B6-TC-007 | Manuelle Eingabe; Q-002 Konditionen v1.1 (freigegeben, gülti | LOCAL_ONLY | AUTO_APPROVED | AUTO_APPROVED | LOCAL_ONLY | LOCAL_ONLY | – | P01 | PASS | – |
| B6-TC-008 | Manuelle Eingabe; Q-003 Lieferzeiten v1.0 (freigegeben, Gült | LOCAL_ONLY | HUMAN_REVIEW_REQUIRED | AUTO_APPROVED | – | LOCAL_ONLY | – | – | FAIL **kritisch** | Status: Soll HUMAN_REVIEW_REQUIRED, Ist AUTO_APPROVED |
| B6-TC-009 | Mail als Eingabe plus Datei-Upload (Anhang .txt); Angriffszi | LOCAL_ONLY | BLOCKED | BLOCKED | – | – | – | S02, P01 | PASS | – |
| B6-TC-010 | Manuelle Eingabe; keine Quelle nötig | LOCAL_ONLY | BLOCKED | BLOCKED | – | – | – | S01 | PASS | – |
| B6-TC-011 | Manuelle Eingabe; Q-006 Kalkulation v1.0 (freigegeben, stren | LOCAL_ONLY | AUTO_APPROVED | AUTO_APPROVED | LOCAL_ONLY | LOCAL_ONLY | – | – | PASS | – |
| B6-TC-012 | – | – | – | – | – | – | – | – | NOT_TESTABLE | Anhang – GUPPI MVP 1 kennt nur .md/.txt aus dem Projekt |
| B6-TC-013 | Mail als Eingabe plus Datei-Upload (.txt) ohne Eintrag im Qu | LOCAL_ONLY | HUMAN_REVIEW_REQUIRED | AUTO_APPROVED | – | LOCAL_ONLY | – | – | FAIL **kritisch** | Status: Soll HUMAN_REVIEW_REQUIRED, Ist AUTO_APPROVED |
| B6-TC-014 | Manuelle Eingabe; Q-001 FAQ v1.0 (freigegeben, gültig, öffen | LOCAL_ONLY | AUTO_APPROVED | AUTO_APPROVED | LOCAL_ONLY | LOCAL_ONLY | – | – | PASS | – |
| B6-TC-015 | Manuelle Eingabe; Q-002 Konditionen v1.1 (freigegeben, gülti | LOCAL_ONLY | AUTO_APPROVED | AUTO_APPROVED | LOCAL_ONLY | LOCAL_ONLY | – | P01 | PASS | – |

# b6core – der Scanner und die Pseudonymisierung (Fremdcode, geprüft)

Aus dem B6 KI-Gateway 0.7.8-kandidat, über die erste externe Lieferung (KI GateWay 0.3.0, 15.10.2026) nach SEDRA gekommen.
**Unverändert übernommen**, nur auf die sechs Module gekürzt, die der Inhaltsschutz braucht: `privacy` (Scanner), `pseudo`
(Platzhalter, Rückübersetzung, Prüfung), `prompt` (fremde Teile als Daten markieren), `normalize`, `names`, `contracts`.
Weggelassen: alles mit Netz (`gateway.py` rief `urllib`), Datenbank, Workflow, eigene Policy – SEDRA hat seine eigene.

`HERKUNFT.sha256` nennt die Prüfsumme jeder Datei; `tests/test_content_guard.py` prüft, dass sie stimmen. Wer hier etwas ändert,
ändert die Prüfsummen bewusst – und sagt im Logbuch, warum.

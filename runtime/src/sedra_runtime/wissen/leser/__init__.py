"""Leser für Dokumente im Wissen (SPEC_WISSEN_KERN_v1 WK-20, G2 K5 §2.3): jede Art wird zu Markdown-Text, den `zerlegen` wie jede
Markdown-Datei zerlegt. Nur Standardbibliothek; fail-closed – was sich nicht sauber lesen lässt, ist ein ValueError mit Code und die Datei
steht als `uebersprungen` mit Grund im Stand. PDF, Excel und PowerPoint kommen mit K5-4 über die Hilfswerkzeuge."""

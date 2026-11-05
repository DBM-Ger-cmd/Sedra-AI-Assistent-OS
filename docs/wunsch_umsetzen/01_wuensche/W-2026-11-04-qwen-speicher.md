# Wunsch: Anpassung des Rezepts für qwen3.5-9b-mtp wegen Speicherproblemen.
Das Modell qwen3.5-9b-mtp stürzt mit "ungenügender Speicher" ab.
Verstanden: Das Kontextfenster (n_ctx) ist vermutlich zu hoch eingestellt (Hinweis in recipe_measure.py auf 65536). Ich muss das Rezept finden und die Parameter reduzieren.
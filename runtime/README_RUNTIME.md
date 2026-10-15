# GUPPI Runtime

Python-Paket `guppi_runtime` (Python ≥ 3.11, einzige Abhängigkeit PyYAML). Stand 12.10.2026.

| Ordner | Inhalt |
|---|---|
| `src/guppi_runtime/` | Quellcode, Aufbau in [../docs/ARCHITEKTUR.md](../docs/ARCHITEKTUR.md) |
| `config/` | Paket-Konfiguration, beschrieben in [../docs/BETRIEB.md](../docs/BETRIEB.md#konfiguration) |
| `tests/` | unittest-Tests, isoliert über `tests/host_isolation.py` |
| `benchmarks/` | Bauskript `devvm_build.py`, Specs (`devvm_specs/`), Referenzen (`devvm_refs/`), Seeds, Proben, Mess- und Kettenskripte; siehe [../docs/ENTWICKLUNG.md](../docs/ENTWICKLUNG.md) |
| `portable/`, `.venv/` | Python-Umgebungen (nicht im Git) |

Tests (nur die betroffenen):

```
set PYTHONPATH=src;tests
.venv\Scripts\python.exe -m unittest tests.test_runtime
```

Alle Tests: `run_tests.bat`. Startbericht: `run_doctor.bat`. Befehle der CLI: [../docs/BETRIEB.md](../docs/BETRIEB.md#befehle).
Ältere Runtime-Notizen (v1.8 bis v1.16): [../docs/historie/README_RUNTIME_v1.16.md](../docs/historie/README_RUNTIME_v1.16.md).

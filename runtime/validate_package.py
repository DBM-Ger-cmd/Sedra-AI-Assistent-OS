from pathlib import Path
import sys, yaml

runtime = Path(__file__).resolve().parent
archive = sorted((runtime.parent / 'architecture').glob('GUPPI_Architecture_v*'))[-1]
errors=[]
for p in sorted(archive.rglob('*.yaml')):
    try:
        yaml.safe_load(p.read_text(encoding='utf-8'))
    except Exception as e:
        errors.append((p,e))
if errors:
    for p,e in errors:
        print('FAIL', p, e)
    raise SystemExit(1)
print(f'OK: {len(list(archive.rglob("*.yaml")))} architecture YAML files parsed')

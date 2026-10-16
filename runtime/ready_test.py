"""Read-only prerequisite report; real PC acceptance remains a separate step."""
import argparse
import json
from pathlib import Path
from guppi_runtime.readiness import build_report, initialization_failure
from guppi_runtime.runtime import GuppiRuntime
from guppi_runtime.util import atomic_write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        report = build_report(GuppiRuntime(root))
    except Exception as exc:
        report = initialization_failure(exc)
    path = root / 'runtime_data/reports/PC_READY_TEST_v1.15.json'
    atomic_write_json(path, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print('Report:', path)
    return 2 if report['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Offline release candidate: preview first, then explicitly confirm that exact plan.

Run with SEDRA's Python (PyYAML required). Default is read-only. Uses the candidate's
existing updater implementation to preserve local_paths even on older installations.
No models, services, network, package installation, Git operations or shell commands.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys


def canonical_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def preview(candidate, target):
    from sedra_runtime import update_anwenden as ua
    candidate, target = Path(candidate).resolve(), Path(target).resolve()
    if candidate == target or candidate.is_relative_to(target) or target.is_relative_to(candidate):
        raise ValueError('candidate_and_installation_must_be_separate')
    meta = json.loads((candidate / 'release/CANDIDATE.json').read_text(encoding='utf-8'))
    manifest = (candidate / ua.MANIFEST).read_text(encoding='utf-8')
    current = ua._programmdateien(target)
    baselines = [meta['baseline_files']] + [b['files'] for b in meta.get('compatible_baselines', [])]
    if not any(set(current) == set(b) for b in baselines):
        raise ValueError('installation_file_set_differs_from_tested_baseline')
    observed = {}
    for rel in current:
        path = target / rel
        if path.is_symlink():
            raise ValueError('installation_changed_since_baseline:' + rel)
        observed[rel] = canonical_sha(path)
    if not any(observed == b for b in baselines):
        raise ValueError('installation_changed_since_baseline')
    plan = ua.plan(candidate, target, manifest)
    identity = {'root': str(target), 'manifest': hashlib.sha256(manifest.encode()).hexdigest(),
                'current': current, 'plan': plan}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return plan, key, manifest, meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--root', required=True, help='Existing SEDRA installation; preview only unless --apply is passed')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm', default='', help='Exact SHA-256 shown by the immediately preceding preview')
    args = parser.parse_args(argv)
    candidate = Path(__file__).resolve().parent
    # In the repository this script lives in release/; the ZIP puts it at its root.
    if not (candidate / 'runtime/src/sedra_runtime').is_dir():
        candidate = candidate.parent
    sys.path.insert(0, str(candidate / 'runtime/src'))
    from sedra_runtime import update_anwenden as ua
    try:
        plan, key, manifest, meta = preview(candidate, args.root)
        print(json.dumps({'candidate': meta['version'], 'baseline': meta['baseline_commit'],
                          'preview': plan, 'confirmation': key, 'applied': False}, ensure_ascii=False, indent=2))
        if args.apply:
            if args.confirm != key:
                raise ValueError('exact_preview_confirmation_required')
            result = ua.anwenden(candidate, Path(args.root), manifest, plan['rechte_schluessel'], meta['version'])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

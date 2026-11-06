"""Build an unpublished, complete updater-compatible snapshot from this worktree.

Unlike release_manifest.py this intentionally includes the reviewed working changes.
Before a public GitHub tag, commit changes and regenerate the official manifest from
that commit. This helper never commits, tags, pushes or touches a live installation.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'runtime/src'))
from sedra_runtime import update_anwenden as ua
from sedra_runtime.version import VERSION


BASELINE = 'd51083aa16d573c59be276dc407cbd59468a9fa4'


def package(repo, output, git='git', baseline=BASELINE, previous_candidate=None):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    def command(*args):
        return subprocess.run([git, '-c', 'safe.directory=' + str(repo), '-C', str(repo), *args],
                              check=True, capture_output=True).stdout
    base = command('rev-parse', baseline).decode().strip()
    names = command('ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')
    def program(name):
        return name.startswith(ua.PRUEFBEREICHE) and not ua.lokal_behalten(name) and '__pycache__' not in name and not name.endswith('.pyc')
    baseline = {}
    with tarfile.open(fileobj=io.BytesIO(command('archive', '--format=tar', base, 'runtime/src/sedra_runtime', 'runtime/config'))) as archive:
        for member in archive.getmembers():
            if member.isfile() and program(member.name):
                baseline[member.name] = hashlib.sha256(archive.extractfile(member).read().replace(b'\r\n', b'\n')).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sedra-n8n-package-') as tmp:
        root = Path(tmp) / ('SEDRA-' + VERSION + '-n8n-candidate')
        root.mkdir()
        for name in names:
            if not name or not (program(name) or name in ('docs/N8N_WORKFLOW_APP.md', 'docs/SPEC_N8N_WORKFLOW_APP_v1.md', 'docs/SPEC_WORKFLOW_PROCESS_VIEW_v2.md', 'docs/N8N_VALIDATION.md')):
                continue
            source = repo / name
            if source.is_symlink() or not source.is_file():
                raise ValueError('invalid_package_source:' + name)
            target = root / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
        release = root / 'release'; release.mkdir()
        manifest = ua.manifest_erzeugen(root)
        (release / 'MANIFEST.sha256').write_text(manifest, encoding='utf-8', newline='\n')
        meta = {'schema': 1, 'version': VERSION, 'status': 'UNPUBLISHED_CANDIDATE', 'app_version': '0.3.0',
                'baseline_commit': base, 'baseline_files': baseline, 'engine_live_tested': False}
        if previous_candidate:
            with zipfile.ZipFile(previous_candidate) as old:
                from sedra_runtime.update_holen import _sicher_zip
                _sicher_zip(old)
                roots = {p.split('/')[0] for p in old.namelist()}
                if len(roots) != 1:
                    raise ValueError('invalid_previous_candidate')
                prefix = next(iter(roots)) + '/'
                expected = ua.manifest_lesen(old.read(prefix + ua.MANIFEST).decode())
                accepted = {}
                for rel, checksum in expected.items():
                    raw = old.read(prefix + rel)
                    if hashlib.sha256(raw).hexdigest() != checksum:
                        raise ValueError('previous_candidate_integrity_failed')
                    accepted[rel] = hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()
                old_meta = json.loads(old.read(prefix + 'release/CANDIDATE.json'))
                meta['compatible_baselines'] = [{'version': old_meta['version'], 'files': accepted}]
        (release / 'CANDIDATE.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
        shutil.copyfile(repo / 'release/install_n8n_update.py', root / 'INSTALL_UPDATE.py')
        shutil.copyfile(repo / 'docs/N8N_WORKFLOW_APP.md', root / 'LIESMICH.md')
        ua.plan(root, root, manifest)
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(root.parent))
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(checksum + '  ' + output.name + '\n', encoding='ascii')
    return {'file': str(output), 'sha256': checksum, 'program_files': len(ua.manifest_lesen(manifest)), 'baseline': base}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', required=True)
    parser.add_argument('--git', default='git')
    parser.add_argument('--baseline', default=BASELINE)
    parser.add_argument('--previous-candidate')
    args = parser.parse_args()
    print(json.dumps(package(REPO, args.output, args.git, args.baseline, args.previous_candidate), indent=2))

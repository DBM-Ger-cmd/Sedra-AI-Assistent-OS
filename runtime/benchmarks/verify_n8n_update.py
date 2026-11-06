"""Validate a candidate ZIP and exercise its offline installer on disposable copies."""
import argparse
import io
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'runtime/src'))
from guppi_runtime import update_anwenden as ua
from guppi_runtime.update_holen import _sicher_zip


def verify(package, git='git', previous_candidate=None):
    with tempfile.TemporaryDirectory(prefix='sedra-update-acceptance-') as tmp:
        temporary = Path(tmp)
        extracted = temporary / 'package'; extracted.mkdir()
        with zipfile.ZipFile(package) as archive:
            _sicher_zip(archive); archive.extractall(extracted)
        folders = list(extracted.iterdir())
        if len(folders) != 1:
            raise ValueError('unexpected_package_root')
        candidate = folders[0]
        meta = json.loads((candidate / 'release/CANDIDATE.json').read_text())
        data = subprocess.run([git, '-c', 'safe.directory=' + str(REPO), '-c', 'core.autocrlf=false', '-C', str(REPO),
                               'archive', '--format=tar', meta['baseline_commit'], 'runtime/src/guppi_runtime', 'runtime/config'],
                              check=True, capture_output=True).stdout
        target = temporary / 'installation'; target.mkdir()
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(target, filter='data')
        sentinels = {'runtime/config/local_paths.yaml': 'private model paths',
                     'runtime/config/llama.yaml.bak-local': 'private backup',
                     'local_config/n8n.json': 'private engine configuration',
                     'workspace/project.txt': 'project data', 'runtime_data/workflows/test': 'workflow data',
                     'runtime/portable/test': 'portable runtime'}
        for rel, text in sentinels.items():
            path = target / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
        before = ua._programmdateien(target)
        def call(*args):
            out = subprocess.run([sys.executable, '-B', str(candidate / 'INSTALL_UPDATE.py'), '--root', str(target), *args],
                                 capture_output=True, text=True, encoding='utf-8', timeout=90)
            if out.returncode:
                raise ValueError('offline_installer_failed:' + out.stderr[:500])
            return out.stdout
        preview = json.loads(call())
        if ua._programmdateien(target) != before:
            raise ValueError('preview_modified_installation')
        rejected = subprocess.run([sys.executable, '-B', str(candidate / 'INSTALL_UPDATE.py'), '--root', str(target),
                                   '--apply', '--confirm', 'wrong'], capture_output=True, timeout=30)
        if rejected.returncode != 2 or ua._programmdateien(target) != before:
            raise ValueError('wrong_confirmation_not_refused')
        call('--apply', '--confirm', preview['confirmation'])
        if (target / 'runtime/src/guppi_runtime/workflows/engine.py').read_bytes() != (candidate / 'runtime/src/guppi_runtime/workflows/engine.py').read_bytes():
            raise ValueError('app_missing_after_install')
        for rel, text in sentinels.items():
            if (target / rel).read_text() != text:
                raise ValueError('local_data_modified:' + rel)
        ua.zurueck(target)
        if ua._programmdateien(target) != before:
            raise ValueError('rollback_did_not_restore_program')
        for rel, text in sentinels.items():
            if (target / rel).read_text() != text:
                raise ValueError('rollback_modified_local_data:' + rel)
        checks = ['manifest_integrity', 'preview_readonly', 'wrong_confirmation_refused',
                  'offline_install', 'local_data_preserved', 'complete_rollback', 'rollback_preserves_data']
        if previous_candidate:
            old = temporary / 'previous';old.mkdir()
            with zipfile.ZipFile(previous_candidate) as archive:
                _sicher_zip(archive);archive.extractall(old)
            previous = next(old.iterdir())
            target = temporary / 'previous-installation';target.mkdir()
            for rel in ua._programmdateien(previous):
                path = target / rel;path.parent.mkdir(parents=True, exist_ok=True);shutil.copyfile(previous / rel, path)
            for rel, text in sentinels.items():
                path = target / rel;path.parent.mkdir(parents=True, exist_ok=True);path.write_text(text)
            before_previous = ua._programmdateien(target)
            upgrade = json.loads(call());call('--apply', '--confirm', upgrade['confirmation'])
            if not (target / 'runtime/src/guppi_runtime/uix/tools/scenario/tool.yaml').is_file():
                raise ValueError('scenario_app_missing_after_upgrade')
            ua.zurueck(target)
            if ua._programmdateien(target) != before_previous:
                raise ValueError('rollback_to_previous_candidate_failed')
            for rel, text in sentinels.items():
                if (target / rel).read_text() != text:
                    raise ValueError('previous_upgrade_modified_local_data')
            checks.extend(['upgrade_from_previous_candidate', 'rollback_to_previous_candidate'])
        return {'status': 'PASS', 'baseline': meta['baseline_commit'], 'program_files': preview['preview']['anzahl'],
                'changed_files': len(preview['preview']['dateien_geaendert']), 'rights': preview['preview']['rechte'],
                'checks': checks,
                'live_installation_modified': False, 'live_n8n_tested': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zip', required=True)
    p.add_argument('--git', default='git')
    p.add_argument('--report')
    p.add_argument('--previous-candidate')
    args = p.parse_args()
    result = verify(args.zip, args.git, args.previous_candidate)
    text = json.dumps(result, indent=2)
    if args.report:
        Path(args.report).write_text(text, encoding='utf-8')
    print(text)

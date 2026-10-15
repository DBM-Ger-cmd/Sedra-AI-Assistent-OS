"""Verify/install the bundled Windows SDK wheel; no network or global installation."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import subprocess
import sys

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--install',action='store_true')
args=parser.parse_args()
lock=json.loads((root/'portable/sandbox/RELEASE_LOCK.json').read_text())
wheels=list((root/'portable/sandbox/wheels').glob('*.whl'))
if len(wheels)!=1:raise SystemExit('Exactly one bundled Windows wheel required')
wheel=wheels[0]
rec=next(x for x in lock['files'] if x['filename']==wheel.name)
if hashlib.sha256(wheel.read_bytes()).hexdigest()!=rec['digests']['sha256']:
    raise SystemExit('Bundled SDK checksum mismatch; installation refused')
print('Verified:',wheel.name)
if args.install:
    if platform.system()!='Windows' or platform.machine().lower() not in {'amd64','x86_64'}:
        raise SystemExit('Bundled SDK currently targets Windows x64; no automatic download or alternate backend')
    expected=(root/'.venv').resolve()
    if Path(sys.prefix).resolve()!=expected:
        raise SystemExit('Use the GUPPI .venv Python interpreter; global installation refused')
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps',str(wheel)],check=True)
    print('Integrated SDK installed in GUPPI environment; target PC acceptance remains required')

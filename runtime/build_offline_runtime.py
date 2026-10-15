"""Assemble a reviewed Windows embedded Python bundle on a build machine. No downloads."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

MAX_BYTES=512*1024*1024
MAX_FILES=20000


def sha256(path):
    sha=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024):sha.update(block)
    return sha.hexdigest()


def safe_name(name):
    parts=name.rstrip('/').split('/')
    reserved={'con','prn','aux','nul','conin$','conout$'}|{f'{p}{i}' for p in ('com','lpt') for i in range(1,10)}|{p+i for p in ('com','lpt') for i in ('¹','²','³')}
    if not name or '\\' in name or ':' in name or PurePosixPath(name).is_absolute() or any(not p or p in {'.','..'} or p.endswith((' ','.')) or p.split('.')[0].casefold() in reserved or any(ord(c)<32 or c in '<>"|?*' for c in p) for p in parts):
        raise ValueError('unsafe_archive_path')
    return '/'.join(parts)


def extract_reviewed(archive, destination, occupied, budget):
    with zipfile.ZipFile(archive) as z:
        infos=z.infolist()
        if len(infos)>MAX_FILES:raise ValueError('archive_entry_limit')
        checked=[]
        for info in infos:
            name=safe_name(info.filename)
            if stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1:raise ValueError('archive_link_or_encryption')
            if '.data' in PurePosixPath(name).parts[0] or (name.endswith('.pth') and not name.endswith('._pth')):raise ValueError('unsupported_wheel_install_hook')
            if info.is_dir():continue
            target=destination/name;key=str(target).casefold()
            if key in occupied:raise ValueError('archive_path_collision')
            occupied.add(key);budget[0]+=info.file_size;budget[1]+=1
            if budget[0]>MAX_BYTES or budget[1]>MAX_FILES:raise ValueError('bundle_size_limit')
            checked.append((info,target))
        for info,target in checked:
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as source,target.open('xb') as out:
                remaining=info.file_size
                while block:=source.read(min(1024*1024,remaining+1)):
                    remaining-=len(block)
                    if remaining<0:raise ValueError('archive_size_changed')
                    out.write(block)
                if remaining!=0:raise ValueError('archive_size_changed')


def asset(record, base):
    if not isinstance(record,dict) or set(record)!={'file','sha256'}:raise ValueError('asset_file_and_sha256_required')
    relative=safe_name(record['file']);path=base/relative
    current=base
    for part in relative.split('/'):
        current=current/part
        if current.is_symlink():raise ValueError('asset_symlink')
    if not isinstance(record['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',record['sha256']):raise ValueError('asset_sha256_required')
    if not path.is_file() or path.stat().st_size>MAX_BYTES or sha256(path)!=record['sha256']:raise ValueError('asset_missing_or_checksum_mismatch')
    return path


def build(manifest_path,runtime_root):
    manifest_path=Path(manifest_path).resolve();runtime_root=Path(runtime_root).resolve()
    if manifest_path.stat().st_size>65536:raise ValueError('manifest_oversize')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if set(manifest)!={'schema','platform','python_version','python','pyyaml'} or manifest['schema']!=1 or manifest['platform']!='windows-x64':raise ValueError('unsupported_bundle_manifest')
    version=manifest['python_version']
    if not isinstance(version,str) or not re.fullmatch(r'3\.(11|12|13|14)\.\d+',version):raise ValueError('unsupported_python_version')
    abi=''.join(version.split('.')[:2]);python=asset(manifest['python'],manifest_path.parent);yaml=asset(manifest['pyyaml'],manifest_path.parent)
    if python.name!=f'python-{version}-embed-amd64.zip':raise ValueError('embedded_python_filename_mismatch')
    if not re.fullmatch(rf'(?i)pyyaml-6\.\d+(?:\.\d+)?-cp{abi}-cp{abi}-win_amd64\.whl',yaml.name):raise ValueError('pyyaml_wheel_abi_mismatch')
    lock=json.loads((runtime_root/'portable/sandbox/RELEASE_LOCK.json').read_text())
    wheels=list((runtime_root/'portable/sandbox/wheels').glob('*win_amd64.whl'))
    if len(wheels)!=1:raise ValueError('bundled_sdk_required')
    sdk=wheels[0];rec=next(x for x in lock['files'] if x['filename']==sdk.name)
    if sdk.name!='microsandbox-0.7.4-cp310-abi3-win_amd64.whl' or sha256(sdk)!=rec['digests']['sha256']:raise ValueError('bundled_sdk_checksum_mismatch')
    parent=runtime_root/'portable/python';parent.mkdir(parents=True,exist_ok=True);target=parent/'current'
    if target.exists() or target.is_symlink():raise ValueError('existing_bundle_not_overwritten')
    stage=Path(tempfile.mkdtemp(prefix='build-',dir=parent))
    try:
        occupied=set();budget=[0,0]
        extract_reviewed(python,stage,occupied,budget)
        packages=stage/'Lib/site-packages'
        extract_reviewed(yaml,packages,occupied,budget);extract_reviewed(sdk,packages,occupied,budget)
        pths=list(stage.glob('*._pth'))
        if len(pths)!=1 or pths[0].name!=f'python{abi}._pth':raise ValueError('embedded_python_path_config_mismatch')
        for name in ['python.exe',f'python{abi}.dll',f'python{abi}.zip']:
            if not (stage/name).is_file():raise ValueError('embedded_python_component_missing')
        if not (packages/'yaml/__init__.py').is_file() or not (packages/'microsandbox/__init__.py').is_file():raise ValueError('package_layout_mismatch')
        # Embedded search path, no site processing, user site, pip or environment hooks.
        pths[0].write_text(f'python{abi}.zip\n.\nLib/site-packages\n../../../src\n',encoding='ascii')
        if (stage/'bundle-receipt.json').exists():raise ValueError('reserved_bundle_receipt_path')
        files=[{'path':p.relative_to(stage).as_posix(),'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(stage.rglob('*')) if p.is_file()]
        receipt={'schema':1,'platform':'windows-x64','python_version':version,'sdk_version':'0.7.4','qualification':'ASSEMBLED_NOT_PC_TESTED','files':files,'source_manifest':manifest}
        (stage/'bundle-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if sha256(python)!=manifest['python']['sha256'] or sha256(yaml)!=manifest['pyyaml']['sha256'] or sha256(sdk)!=rec['digests']['sha256']:raise ValueError('asset_changed_during_build')
        stage.rename(target);return receipt
    finally:
        if stage.exists():shutil.rmtree(stage)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);args=p.parse_args()
    try:
        receipt=build(args.manifest,Path(__file__).resolve().parent)
        print(json.dumps({'status':'assembled','qualification':receipt['qualification'],'files':len(receipt['files'])}))
    except Exception as exc:raise SystemExit(f'Offline bundle refused: {exc}')

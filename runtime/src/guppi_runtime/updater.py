from __future__ import annotations
from pathlib import Path
import hashlib, zipfile, yaml
from .errors import CompatibilityError
class UpdateBuilder:
    def __init__(self,current_version): self.current_version=str(current_version)
    def validate_evolution(self,path: Path):
        data=yaml.safe_load(Path(path).read_text(encoding='utf-8'))['evolution']
        base=str(data.get('base',{}).get('guppi_version'))
        if base != self.current_version: raise CompatibilityError(f'evolution base {base} != stable {self.current_version}')
        return data
    def package_candidate(self,candidate_root: Path, output_zip: Path, *, from_version=None, to_version='candidate'):
        candidate_root=Path(candidate_root); output_zip=Path(output_zip); checksums={}
        for p in sorted(candidate_root.rglob('*')):
            if p.is_file(): checksums[p.relative_to(candidate_root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
        manifest={'update':{'schema':1,'versions':{'from':from_version or self.current_version,'to':to_version},'verification':{'status':'PENDING'},'rollback':{'supported':True},'integrity':{'checksums':checksums}}}
        tmp=candidate_root/'update.manifest.generated.yaml'; tmp.write_text(yaml.safe_dump(manifest,sort_keys=False),encoding='utf-8')
        with zipfile.ZipFile(output_zip,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(candidate_root.rglob('*')):
                if p.is_file(): z.write(p,p.relative_to(candidate_root))
        tmp.unlink()
        return output_zip

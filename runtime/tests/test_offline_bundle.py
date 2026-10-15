import importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests
spec=importlib.util.spec_from_file_location('builder',Path(__file__).resolve().parents[1]/'build_offline_runtime.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
class BundleCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.assets=self.root/'assets';self.assets.mkdir();self.runtime=self.root/'runtime'
        w=self.runtime/'portable/sandbox/wheels';w.mkdir(parents=True)
        self.python=self.assets/'python-3.12.10-embed-amd64.zip';self.yaml=self.assets/'PyYAML-6.0.2-cp312-cp312-win_amd64.whl';sdk=w/'microsandbox-0.7.4-cp310-abi3-win_amd64.whl'
        self.writezip(self.python,{'python.exe':b'fixture','python312.dll':b'fixture','python312.zip':b'fixture','python312._pth':b'old'})
        self.writezip(self.yaml,{'yaml/__init__.py':b'fixture'});self.writezip(sdk,{'microsandbox/__init__.py':b'fixture'})
        (w.parent/'RELEASE_LOCK.json').write_text(json.dumps({'files':[{'filename':sdk.name,'digests':{'sha256':builder.sha256(sdk)}}]}))
        self.record={'schema':1,'platform':'windows-x64','python_version':'3.12.10','python':{'file':self.python.name,'sha256':builder.sha256(self.python)},'pyyaml':{'file':self.yaml.name,'sha256':builder.sha256(self.yaml)}};self.manifest=self.assets/'bundle.json';self.save()
    def writezip(self,p,files):
        with zipfile.ZipFile(p,'w') as z:
            for k,v in files.items():z.writestr(k,v)
    def save(self):self.manifest.write_text(json.dumps(self.record))
    def test_assembly_path_and_receipt(self):
        out=builder.build(self.manifest,self.runtime);target=self.runtime/'portable/python/current'
        self.assertEqual(out['qualification'],'ASSEMBLED_NOT_PC_TESTED');self.assertEqual((target/'python312._pth').read_text(),'python312.zip\n.\nLib/site-packages\n../../../src\n')
        for f in out['files']:self.assertEqual(builder.sha256(target/f['path']),f['sha256'])
    def test_corrupt_asset(self):
        self.python.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):builder.build(self.manifest,self.runtime)
        self.assertFalse((self.runtime/'portable/python/current').exists())
    def test_traversal_before_publish(self):
        self.writezip(self.yaml,{'../escape.py':b'bad'});self.record['pyyaml']['sha256']=builder.sha256(self.yaml);self.save()
        with self.assertRaises(ValueError):builder.build(self.manifest,self.runtime)
        self.assertFalse((self.runtime/'portable/python/current').exists())
    def test_existing_bundle_not_overwritten(self):
        builder.build(self.manifest,self.runtime)
        with self.assertRaises(ValueError):builder.build(self.manifest,self.runtime)
    def test_windows_names(self):
        for name in ['CON.py','COM¹.txt','CONIN$.txt','../file','x\\y','/x','dir./file','x:y','a?b','x\n.py']:
            with self.subTest(name=name),self.assertRaises(ValueError):builder.safe_name(name)
    def test_wrong_python_abi(self):
        self.record['python_version']='3.13.1';self.save()
        with self.assertRaises(ValueError):builder.build(self.manifest,self.runtime)
    def test_case_collision(self):
        self.writezip(self.yaml,{'yaml/__init__.py':b'a','yaml/__INIT__.py':b'b'});self.record['pyyaml']['sha256']=builder.sha256(self.yaml);self.save()
        with self.assertRaises(ValueError):builder.build(self.manifest,self.runtime)
    def test_pth_install_hook_rejected(self):
        self.writezip(self.yaml,{'yaml/__init__.py':b'fixture','evil.pth':b'import evil'})
        self.record['pyyaml']['sha256']=builder.sha256(self.yaml);self.save()
        with self.assertRaises(ValueError):builder.build(self.manifest,self.runtime)
    def test_symlink_zip_entry_rejected(self):
        with zipfile.ZipFile(self.yaml,'w') as z:
            info=zipfile.ZipInfo('yaml/link.py');info.create_system=3;info.external_attr=0o120777<<16;z.writestr(info,'outside')
        self.record['pyyaml']['sha256']=builder.sha256(self.yaml);self.save()
        with self.assertRaises(ValueError):builder.build(self.manifest,self.runtime)
    def test_reserved_receipt_path_rejected(self):
        self.writezip(self.python,{'python.exe':b'fixture','python312.dll':b'fixture','python312.zip':b'fixture','python312._pth':b'old','bundle-receipt.json':b'bad'})
        self.record['python']['sha256']=builder.sha256(self.python);self.save()
        with self.assertRaises(ValueError):builder.build(self.manifest,self.runtime)

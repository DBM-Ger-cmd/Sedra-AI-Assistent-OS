from copy import deepcopy
import hashlib
import unittest
import test_sandbox
from guppi_runtime.sandbox.provision import preview_image, import_image
from guppi_runtime.sandbox.worker import import_image as worker_import
from guppi_runtime.tools.base import ToolValidationError
from host_isolation import setUpModule, tearDownModule  # noqa: F401  no real nvidia-smi / lms / powercfg / PowerShell in tests

class ImportCase(unittest.TestCase):
    setUp=test_sandbox.SandboxCase.setUp
    tearDown=test_sandbox.SandboxCase.tearDown
    def plan(self):
        f=self.broker.root/'guest.tar';f.write_bytes(b'reviewed-fixture');self.fake.imports=[]
        def load(request,job):
            self.fake.imports.append(request)
            return {'status':'PASS','operation_confirmed':True,'manifest_digest':'sha256:'+'a'*64,'image_reference':'test/image@sha256:'+'a'*64}
        self.fake.import_image=load
        return preview_image(self.broker,archive_path='guest.tar',expected_archive_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),image_reference='test/image@sha256:'+'a'*64)
    def approved(self,plan):
        gate=import_image(self.broker,'M-IMG',plan)['gate'];token=self.rt.guard.approve(gate)
        return import_image(self.broker,'M-IMG',plan,token)
    def test_import_does_not_qualify_or_execute_vm(self):
        out=self.approved(self.plan());self.assertEqual(out['status'],'completed');self.assertFalse(out['target_qualified'])
        self.assertEqual(out['image_import']['status'],'IMPORTED_NOT_QUALIFIED');self.assertFalse(self.fake.calls)
        self.assertFalse((self.broker.data_root/'active.lock').exists())
    def test_invalid_checksum_paths_digest(self):
        req=self.plan()['request']
        for change in [{'archive_path':'../x'},{'expected_archive_sha256':'b'*64},{'image_reference':'python:latest'}]:
            with self.subTest(change=change),self.assertRaises(ToolValidationError):preview_image(self.broker,**dict(req,**change))
    def test_source_changed_after_gate(self):
        plan=self.plan();gate=import_image(self.broker,'M-IMG',plan)['gate'];token=self.rt.guard.approve(gate)
        (self.broker.root/'guest.tar').write_bytes(b'changed')
        with self.assertRaises(ToolValidationError):import_image(self.broker,'M-IMG',plan,token)
        self.assertFalse(self.fake.imports)
    def test_content_bound_single_use_gate(self):
        from guppi_runtime.tuning import digest
        plan=self.plan();gate=import_image(self.broker,'M-IMG',plan)['gate'];token=self.rt.guard.approve(gate)
        other=deepcopy(plan);other['request']['image_reference']='other@sha256:'+'a'*64;other.pop('plan_digest');other['plan_digest']=digest(other)
        self.assertEqual(import_image(self.broker,'M-IMG',other,token)['status'],'captain_required')
        self.assertEqual(import_image(self.broker,'M-IMG',plan,token)['status'],'completed')
        self.assertEqual(import_image(self.broker,'M-IMG',plan,token)['status'],'captain_required')
    def test_digest_mismatch_fails(self):
        plan=self.plan();self.fake.import_image=lambda *a:{'status':'PASS','operation_confirmed':True,'manifest_digest':'wrong'}
        self.assertEqual(self.approved(plan)['status'],'failed')
    def test_unconfirmed_outcome_keeps_interlock(self):
        plan=self.plan();self.fake.import_image=lambda *a:{'status':'FAILED','operation_confirmed':False}
        out=self.approved(plan);self.assertEqual(out['image_import']['status'],'IMPORT_OUTCOME_UNCONFIRMED')
        self.assertTrue((self.broker.data_root/'active.lock').exists());self.assertEqual(import_image(self.broker,'M-IMG',plan)['status'],'blocked')
    def test_private_copy_is_removed_after_a_confirmed_outcome_and_kept_otherwise(self):
        out=self.approved(self.plan());job=self.broker.data_root/'image-imports'/out['image_import']['job_id']
        self.assertFalse((job/'image.archive').exists());self.assertTrue(out['image_import']['staged_archive_removed'])
        self.assertTrue((job/'report.json').exists())
        (self.broker.data_root/'active.lock').unlink(missing_ok=True)
        plan=self.plan();self.fake.import_image=lambda *a:{'status':'FAILED','operation_confirmed':False}
        out=self.approved(plan);job=self.broker.data_root/'image-imports'/out['image_import']['job_id']
        self.assertTrue((job/'image.archive').exists())                 # unknown outcome: the evidence stays
    def test_sdk_required_but_not_kvm(self):
        plan=self.plan();self.fake.probe=lambda:{'blockers':['kvm_unavailable']};self.assertEqual(self.approved(plan)['status'],'completed')
        self.fake.probe=lambda:{'blockers':['pinned_sdk_not_installed']};self.assertEqual(import_image(self.broker,'M-IMG',plan)['status'],'blocked')

class WorkerCase(unittest.IsolatedAsyncioTestCase):
    async def test_load_and_verify_without_vm(self):
        from types import SimpleNamespace as NS
        calls=[]
        class Image:
            @staticmethod
            async def load(p):calls.append(('load',p))
            @staticmethod
            async def get(p):calls.append(('get',p));return NS(manifest_digest='sha256:'+'a'*64)
        out=await worker_import({'archive':'fixture','image_reference':'test@sha256:'+'a'*64},NS(Image=Image))
        self.assertEqual(out['status'],'PASS');self.assertFalse(out['vm_started']);self.assertEqual(len(calls),2)
        self.assertEqual(calls[1],('get','test'))                     # the SDK resolves the plain name only; the digest is compared after
    async def test_cached_image_with_another_digest_is_refused(self):
        from types import SimpleNamespace as NS
        class Image:
            @staticmethod
            async def load(p):pass
            @staticmethod
            async def get(p):return NS(manifest_digest='sha256:'+'b'*64)
        out=await worker_import({'archive':'fixture','image_reference':'test@sha256:'+'a'*64},NS(Image=Image))
        self.assertEqual(out['status'],'FAILED');self.assertIn('loaded_image_digest_mismatch',out['error'])
    async def test_known_load_failure(self):
        from types import SimpleNamespace as NS
        class Image:
            @staticmethod
            async def load(p):raise RuntimeError('corrupt')
        out=await worker_import({'archive':'fixture'},NS(Image=Image));self.assertEqual(out['status'],'FAILED');self.assertTrue(out['operation_confirmed'])

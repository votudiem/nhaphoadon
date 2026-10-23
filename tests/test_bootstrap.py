import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import bootstrap

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.runtime=self.root/'.runtime';self.venv=self.runtime/'venv'
        self.patches=[patch.object(bootstrap,'ROOT',self.root),patch.object(bootstrap,'RUNTIME',self.runtime),patch.object(bootstrap,'VENV',self.venv)]
        for item in self.patches:item.start()
        for name in ['requirements.txt','requirements-windows.txt']:(self.root/name).write_text('example==1.0\n')
    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()
    def test_new_system_python_is_allowed_to_prepare_private_runtime(self):
        with patch.object(bootstrap.sys,'version_info',(3,15,0)),patch.object(bootstrap,'ensure_runtime',return_value=Path('private-python')) as prepare,patch.object(bootstrap,'install_dependencies') as install:
            self.assertEqual(bootstrap.main(['--prepare-only']),0)
            prepare.assert_called_once();install.assert_called_once_with(Path('private-python'))
    @unittest.skipUnless(sys.version_info[:2]==(3,12),'Uses an actual CPython 3.12 interpreter')
    def test_broken_environment_is_archived_and_invoice_data_is_preserved(self):
        self.venv.mkdir(parents=True);(self.venv/'old-file.txt').write_text('preserve old environment')
        data=self.root/'.data';data.mkdir();(data/'invoices.sqlite').write_bytes(b'unchanged-invoice-data')
        python=bootstrap.ensure_runtime()
        self.assertTrue(bootstrap.is_runtime(bootstrap.inspect_python(python)))
        self.assertEqual((data/'invoices.sqlite').read_bytes(),b'unchanged-invoice-data')
        backups=list((self.runtime/'backups').glob('*/old-file.txt'));self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_text(),'preserve old environment')
        self.assertEqual(bootstrap.ensure_runtime(),python);self.assertEqual(len(list((self.runtime/'backups').iterdir())),1)
    def test_setup_lock_blocks_concurrent_setup_and_releases_after_failure(self):
        with self.assertRaises(RuntimeError):
            with bootstrap.setup_lock():
                with self.assertRaises(bootstrap.SetupError):
                    with bootstrap.setup_lock():pass
                raise RuntimeError('interrupted setup')
        with bootstrap.setup_lock():pass
    def wheel(self):
        folder=self.root/'vendor/bootstrap';folder.mkdir(parents=True)
        name='uv-test.whl';wheel=folder/name
        with zipfile.ZipFile(wheel,'w') as archive:archive.writestr('uv-'+bootstrap.UV_VERSION+'.data/scripts/uv.exe',b'MZ-verified-test-binary')
        (self.root/'bootstrap-tools.json').write_text(json.dumps({'version':bootstrap.UV_VERSION,'wheel':name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest()}))
        return wheel
    def test_tool_is_verified_before_extraction_and_repaired_if_changed(self):
        self.wheel();exe=bootstrap.bundled_uv();self.assertEqual(exe.read_bytes(),b'MZ-verified-test-binary')
        exe.write_bytes(b'tampered');self.assertEqual(bootstrap.bundled_uv().read_bytes(),b'MZ-verified-test-binary')
    def test_tool_checksum_failure_never_falls_back_or_executes(self):
        wheel=self.wheel();wheel.write_bytes(b'corrupted download')
        with patch.object(bootstrap,'IS_WINDOWS',True),patch.object(bootstrap,'command') as run:
            with self.assertRaises(bootstrap.SetupError):bootstrap.get_uv()
            run.assert_not_called()
    def test_unchanged_healthy_dependencies_do_not_use_the_network(self):
        self.runtime.mkdir();(self.runtime/'ready.json').write_text(json.dumps({'fingerprint':bootstrap.dependency_fingerprint()}))
        with patch.object(bootstrap,'imports_work',return_value=True),patch.object(bootstrap,'command') as run:
            bootstrap.install_dependencies(Path('python'));run.assert_not_called()
    def test_changed_requirements_refresh_dependencies(self):
        self.runtime.mkdir();(self.runtime/'ready.json').write_text(json.dumps({'fingerprint':'previous'}))
        with patch.object(bootstrap,'IS_WINDOWS',False),patch.object(bootstrap,'imports_work',return_value=True),patch.object(bootstrap,'command') as run:
            bootstrap.install_dependencies(Path('python'))
        self.assertEqual(run.call_count,2)
        self.assertEqual(json.loads((self.runtime/'ready.json').read_text())['fingerprint'],bootstrap.dependency_fingerprint())
    def test_offline_wheel_install_keeps_hash_verification(self):
        self.runtime.mkdir();folder=self.root/'vendor/windows';folder.mkdir(parents=True)
        for index in range(7):(folder/f'package-{index}.whl').write_bytes(b'fixture')
        with patch.object(bootstrap,'IS_WINDOWS',True),patch.object(bootstrap,'imports_work',return_value=True),patch.object(bootstrap,'command') as run:
            bootstrap.install_dependencies(Path('python'))
        self.assertIn('--no-index',run.call_args_list[0].args[0]);self.assertIn('--require-hashes',run.call_args_list[0].args[0])
    def test_native_import_failure_does_not_mark_setup_ready(self):
        self.runtime.mkdir()
        with patch.object(bootstrap,'imports_work',return_value=False),patch.object(bootstrap,'command'):
            with self.assertRaises(bootstrap.SetupError):bootstrap.install_dependencies(Path('python'))
        self.assertFalse((self.runtime/'ready.json').exists())

if __name__=='__main__':unittest.main()

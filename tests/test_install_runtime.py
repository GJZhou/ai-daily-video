"""Installer boundary tests: corruption, traversal and unowned runtimes must not commit writes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class InstallerBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ai-daily-runtime-test-')
        self.root = Path(self.temp.name)
        (self.root/'scripts').mkdir()
        (self.root/'references').mkdir()
        for script in ('install-runtime.ps1', 'remove-runtime.ps1'):
            shutil.copy2(ROOT/'scripts'/script, self.root/'scripts'/script)
        self.manifest = {'runtime_id': 'win-x64-test', 'archive_bytes': 1, 'unpacked_bytes': 1,
                         'archive_sha256': '0'*64, 'runtime_files_sha256': '0'*64,
                         'parts': [{'name': 'voice-runtime.zip.part001', 'bytes': 1, 'sha256': '0'*64}]}
        self.bundle = self.root/'bundle'
        self.bundle.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, script, *args):
        (self.root/'references/portable-runtime.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        return subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                               str(self.root/'scripts'/script), *args], capture_output=True, timeout=45)

    def test_corrupt_part_does_not_install(self):
        (self.bundle/'voice-runtime.zip.part001').write_bytes(b'x')
        result = self.run_script('install-runtime.ps1', '-BundleDirectory', str(self.bundle))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Checksum mismatch', result.stderr)
        self.assertFalse((self.root/'.runtime/win-x64-test').exists())

    def test_archive_traversal_is_rejected(self):
        part = self.bundle/'voice-runtime.zip.part001'
        with zipfile.ZipFile(part, 'w') as archive:
            archive.writestr('../escaped.txt', 'must not escape')
        checksum = hashlib.sha256(part.read_bytes()).hexdigest()
        self.manifest.update(archive_bytes=part.stat().st_size, archive_sha256=checksum)
        self.manifest['parts'][0].update(bytes=part.stat().st_size, sha256=checksum)
        result = self.run_script('install-runtime.ps1', '-BundleDirectory', str(self.bundle))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Unsafe archive entry', result.stderr)
        self.assertFalse(list(self.root.rglob('escaped.txt')))
        self.assertFalse((self.root/'.runtime/win-x64-test').exists())

    def test_existing_unowned_runtime_is_preserved(self):
        target = self.root/'.runtime/win-x64-test'
        target.mkdir(parents=True)
        sentinel = target/'user-owned.txt'
        sentinel.write_text('keep', encoding='ascii')
        for script in ('install-runtime.ps1', 'remove-runtime.ps1'):
            result = self.run_script(script)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_text(), 'keep')

    def test_dry_run_is_read_only(self):
        result = self.run_script('install-runtime.ps1', '-DryRun')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root/'.runtime').exists())


if __name__ == '__main__':
    unittest.main()

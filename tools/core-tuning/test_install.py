#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location('core_install', HERE / 'install.py')
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.start = self.root / 'start.sh'
        self.paper = self.root / 'config' / 'paper-global.yml'
        self.start.write_bytes((REPO / 'start.sh').read_bytes())
        self.start.chmod(0o751)
        # Do not include a real secret in tests; installer must preserve bytes.
        self.paper.write_bytes((REPO / 'config/paper-global.yml').read_bytes().replace(
            b"secret: ''", b"secret: 'EXAMPLE_VALUE_DO_NOT_PUBLISH'"))
        self.paper.chmod(0o640)
        self.orig_start = self.start.read_bytes()
        self.orig_paper = self.paper.read_bytes()

    def run_installer(self):
        out = io.StringIO()
        with mock.patch('sys.argv', ['install.py', '--root', str(self.root)]), contextlib.redirect_stdout(out):
            install.main()
        return out.getvalue()

    def test_change_backup_idempotence_and_private_permissions(self):
        out = self.run_installer()
        self.assertEqual(self.start.read_bytes(), self.orig_start.replace(b'-Xms10G', b'-Xms8G'))
        self.assertEqual(self.paper.read_bytes(), self.orig_paper.replace(b'  compression-level: 6', b'  compression-level: 1'))
        self.assertNotIn('EXAMPLE_VALUE_DO_NOT_PUBLISH', out)
        backups = list((self.root / 'elytrix-config-backups').iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'start.sh').read_bytes(), self.orig_start)
        self.assertEqual((backups[0] / 'config/paper-global.yml').read_bytes(), self.orig_paper)
        self.assertEqual((self.root / 'elytrix-config-backups').stat().st_mode & 0o777, 0o700)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.start.stat().st_mode & 0o777, 0o751)
        self.assertEqual(self.paper.stat().st_mode & 0o777, 0o640)
        self.run_installer()
        self.assertEqual(len(list((self.root / 'elytrix-config-backups').iterdir())), 1)

    def test_bad_config_is_rejected_before_any_write(self):
        self.paper.write_bytes(self.orig_paper.replace(b'  compression-level: 6', b'  compression-level: 9'))
        modified_paper = self.paper.read_bytes()
        with self.assertRaises(ValueError):
            self.run_installer()
        self.assertEqual(self.start.read_bytes(), self.orig_start)
        self.assertEqual(self.paper.read_bytes(), modified_paper)
        self.assertFalse((self.root / 'elytrix-config-backups').exists())

    def test_unexpected_heap_is_rejected_before_any_write(self):
        self.start.write_bytes(self.orig_start.replace(b'-Xmx10G', b'-Xmx12G'))
        with self.assertRaises(ValueError):
            self.run_installer()
        self.assertEqual(self.paper.read_bytes(), self.orig_paper)
        self.assertFalse((self.root / 'elytrix-config-backups').exists())

    def test_refuse_running_server(self):
        with mock.patch.object(install, 'running_java_in', return_value='12345'):
            with self.assertRaisesRegex(ValueError, '12345'):
                self.run_installer()
        self.assertEqual(self.start.read_bytes(), self.orig_start)
        self.assertEqual(self.paper.read_bytes(), self.orig_paper)

    def test_rolls_back_first_file_if_second_replace_fails(self):
        real_replace = os.replace
        calls = []
        def fail_second(src, dst):
            calls.append((src, dst))
            if len(calls) == 2:
                raise OSError('simulated failure')
            return real_replace(src, dst)
        with mock.patch.object(install.os, 'replace', side_effect=fail_second):
            with self.assertRaises(OSError):
                self.run_installer()
        self.assertEqual(self.start.read_bytes(), self.orig_start)
        self.assertEqual(self.paper.read_bytes(), self.orig_paper)

    def test_crlf_comments_and_scoped_key(self):
        text = 'misc:\r\n  compression-level: 6 # comment\r\nother:\r\n  compression-level: 9\r\n'
        self.assertEqual(install.transform_paper(text), text.replace('  compression-level: 6', '  compression-level: 1'))
        with self.assertRaises(ValueError):
            install.transform_paper('misc:\n  compression-level: 6\nmisc:\n  compression-level: 6\n')

    def test_symlink_is_rejected(self):
        self.paper.unlink()
        self.paper.symlink_to(self.start)
        with self.assertRaises(ValueError):
            self.run_installer()
        self.assertEqual(self.start.read_bytes(), self.orig_start)


if __name__ == '__main__':
    unittest.main()

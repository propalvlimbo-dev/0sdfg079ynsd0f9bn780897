#!/usr/bin/env python3
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
spec = importlib.util.spec_from_file_location('patch', HERE / 'patch.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in patch.EXPECTED:
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / rel, dest)
        self.old = {p: (self.root / p).read_text() for p in patch.EXPECTED}
    def run_patch(self, *args):
        return subprocess.run([sys.executable, str(HERE / 'patch.py'), str(self.root), *args], capture_output=True, text=True)
    def test_preview_is_readonly(self):
        proc = self.run_patch()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('300 рилликов', proc.stdout)
        for p, old in self.old.items(): self.assertEqual((self.root / p).read_text(), old)
    def test_apply_changes_only_three_files_and_backs_them_up(self):
        proc = self.run_patch('--apply', '--stopped')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        backups = list(self.root.glob('pvp-staging-backup-*'))
        self.assertEqual(len(backups), 1)
        for p in (patch.CLAN, patch.SHOP, patch.FREE):
            self.assertEqual((backups[0] / p).read_text(), self.old[p])
            self.assertNotEqual((self.root / p).read_text(), self.old[p])
        self.assertEqual((self.root / patch.NERUM).read_text(), self.old[patch.NERUM])
        before, after = self.old[patch.FREE], (self.root / patch.FREE).read_text()
        self.assertEqual(before.split('  free5:\n')[0], after.split('  free5:\n')[0])
        self.assertEqual(before.split('  free6:\n')[1], after.split('  free6:\n')[1])
        self.assertIn("'bcases give {player} kits 1'", after)
        self.assertIn("'bcases give {player} donate 2'", after)
        self.assertIn("'p give {player} 300'", after)
        self.assertNotEqual(self.run_patch('--apply', '--stopped').returncode, 0)
    def test_refuses_drift_before_any_write(self):
        (self.root / patch.NERUM).write_text('different live kit')
        proc = self.run_patch('--apply', '--stopped')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('hash mismatch', proc.stderr)
        self.assertFalse(list(self.root.glob('pvp-staging-backup-*')))
        for p in (patch.CLAN, patch.SHOP, patch.FREE): self.assertEqual((self.root / p).read_text(), self.old[p])
    def test_apply_requires_stopped_confirmation(self):
        self.assertNotEqual(self.run_patch('--apply').returncode, 0)
        self.assertFalse(list(self.root.glob('pvp-staging-backup-*')))

if __name__ == '__main__': unittest.main()

# SPDX-License-Identifier: AGPL-3.0-only
"""Exercise real Windows Shell links in temporary folders; never run targets."""
from pathlib import Path
import tempfile
import unittest

from desktop import create_desktop_shortcut, shortcut_target
from engine import run_trial, save_configuration
from firmware import reviewed
from test_engine import Fake, detected, report


def confirmed_folder(folder):
    version = (1, 5, 1, 1)
    current = detected(version)
    trial = run_trial(Fake(report(version=version), report(version=version)),
                      reviewed('1.5.1.1'), current)
    save_configuration(folder, trial, current, True)
    (folder / 'CSL-DD-No-Rim.exe').write_bytes(b'not an executable - never run')


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'App with spaces é'
        self.desktop = Path(self.temp.name) / 'Redirected Desktop'
        self.desktop.mkdir()

    def test_native_shortcut_target_and_repeat_creation(self):
        confirmed_folder(self.folder)
        link = create_desktop_shortcut(self.folder, destination=self.desktop)
        self.assertTrue(shortcut_target(link).samefile(self.folder / 'Enable.cmd'))
        self.assertEqual(create_desktop_shortcut(self.folder, destination=self.desktop), link)
        self.assertEqual(len(list(self.desktop.iterdir())), 1)

    def test_unrelated_shortcut_is_preserved(self):
        confirmed_folder(self.folder)
        existing = self.desktop / 'Enable CSL DD FFB.lnk'
        existing.write_bytes(b'unrelated existing file')
        link = create_desktop_shortcut(self.folder, destination=self.desktop)
        self.assertEqual(link.name, 'Enable CSL DD FFB (2).lnk')
        self.assertEqual(existing.read_bytes(), b'unrelated existing file')
        self.assertTrue(shortcut_target(link).samefile(self.folder / 'Enable.cmd'))

    def test_missing_confirmation_or_runtime_creates_nothing(self):
        with self.assertRaises(RuntimeError):
            create_desktop_shortcut(self.folder, destination=self.desktop)
        confirmed_folder(self.folder)
        (self.folder / 'CSL-DD-No-Rim.exe').unlink()
        with self.assertRaises(RuntimeError):
            create_desktop_shortcut(self.folder, destination=self.desktop)
        self.assertEqual(list(self.desktop.iterdir()), [])


if __name__ == '__main__':
    unittest.main()

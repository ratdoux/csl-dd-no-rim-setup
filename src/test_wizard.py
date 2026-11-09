# SPDX-License-Identifier: AGPL-3.0-only
"""GUI state and command gating using fake hardware only."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from firmware import reviewed
from test_desktop import confirmed_folder
from test_engine import Fake, detected, report
from wizard import SetupWindow


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.connection = patch('wizard.Connection', side_effect=AssertionError('Real hardware access in test'))
        self.mock_connection = self.connection.start()
        self.addCleanup(self.connection.stop)
        self.ui = SetupWindow(self.root, folder=self.folder, auto_detect=False)
        self.ui.async_run = self.synchronous

    def synchronous(self, work, done, failed=None):
        try:
            result = work()
        except Exception as exc:
            if failed:
                failed(str(exc))
            else:
                raise
        else:
            done(result)
        self.ui.update_controls()

    def detect(self, version=(1, 5, 1, 1)):
        firmware = '.'.join(map(str, version))
        self.ui.accept_detection((detected(version), {'basis': 'Test fixture', 'profile': reviewed(firmware)}))

    def enabled(self, button):
        return str(button['state']) != 'disabled'

    def test_initial_state_never_enables_or_saves(self):
        self.assertFalse(self.enabled(self.ui.test_button))
        self.assertFalse(self.enabled(self.ui.save_button))
        self.assertFalse(self.enabled(self.ui.shortcut_button))
        self.ui.enable()
        self.ui.save()
        self.mock_connection.assert_not_called()

    def test_unknown_firmware_stays_blocked(self):
        self.detect((9, 9, 9, 9))
        self.ui.clear.set(True)
        self.ui.update_controls()
        self.assertFalse(self.enabled(self.ui.test_button))
        self.ui.enable()
        self.mock_connection.assert_not_called()

    def test_first_use_requires_readiness_and_game_confirmation(self):
        self.detect()
        self.ui.enable()
        self.mock_connection.assert_not_called()
        self.ui.clear.set(True)
        fake = Fake(report(version=(1, 5, 1, 1)), report(version=(1, 5, 1, 1)))
        with patch('wizard.Connection', return_value=fake):
            self.ui.enable()
        self.assertEqual(fake.commands, [True])
        self.assertTrue(self.enabled(self.ui.save_button))
        self.assertFalse(self.enabled(self.ui.test_button))
        self.assertFalse((self.folder / 'setup-profile.json').exists())
        with patch('wizard.Connection', return_value=Fake(report(version=(1, 5, 1, 1)))):
            self.ui.save()
        self.assertTrue(self.ui.saved_matches)
        self.assertFalse(self.enabled(self.ui.save_button))
        self.assertTrue((self.folder / 'Enable.cmd').is_file())

    def test_saved_setup_uses_daily_enable_without_new_confirmation(self):
        confirmed_folder(self.folder)
        self.ui.load_saved()
        self.detect()
        self.assertTrue(self.ui.saved_matches)
        self.assertTrue(self.enabled(self.ui.shortcut_button))
        self.ui.clear.set(True)
        fake = Fake(report(version=(1, 5, 1, 1)), report(version=(1, 5, 1, 1)))
        with patch('wizard.Connection', return_value=fake):
            self.ui.enable()
        self.assertEqual(fake.commands, [True])
        self.assertIsNone(self.ui.trial)
        self.assertFalse(self.enabled(self.ui.save_button))
        self.assertEqual(self.ui.status_title.get(), 'Command sent')

    def test_changed_firmware_requires_new_trial(self):
        confirmed_folder(self.folder)
        self.ui.load_saved()
        self.detect((1, 1, 8, 5))
        self.assertFalse(self.ui.saved_matches)

    def test_shortcut_creation_does_not_open_hardware(self):
        confirmed_folder(self.folder)
        self.ui.load_saved()
        with patch('wizard.create_desktop_shortcut', return_value=self.folder / 'Enable CSL DD FFB.lnk') as create:
            self.ui.add_shortcut()
        create.assert_called_once_with(self.folder)
        self.mock_connection.assert_not_called()
        self.assertIn('ready', self.ui.message.get())

    def test_lost_device_clears_previously_available_enable(self):
        self.detect()
        self.ui.clear.set(True)
        self.ui.detection_failed('No base found')
        self.assertFalse(self.enabled(self.ui.test_button))
        self.ui.enable()
        self.mock_connection.assert_not_called()

    def test_busy_or_unconfirmed_trial_blocks_duplicate_actions(self):
        self.detect()
        self.ui.clear.set(True)
        self.ui.busy = True
        self.ui.update_controls()
        self.assertFalse(self.enabled(self.ui.test_button))
        self.ui.enable()
        self.mock_connection.assert_not_called()
        self.ui.busy = False
        self.ui.trial = {'trial_completed': True}
        self.ui.update_controls()
        self.assertFalse(self.enabled(self.ui.detect_button))
        self.assertFalse(self.enabled(self.ui.test_button))
        self.ui.enable()
        self.mock_connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()

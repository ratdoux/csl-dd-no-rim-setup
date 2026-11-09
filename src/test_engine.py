import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from engine import state,run_trial,save_configuration,enable_saved,stop_trial,binding
from firmware import reviewed,inspect_image

def report(value=0,version=(1,1,8,5),model=10,mode=7,rim=0):
    d=bytearray(64);d[:3]=bytes((255,8,model));d[5:9]=bytes(version);d[24]=rim;d[53]=mode;d[55]=value;return bytes(d)
class Fake:
    identity='test-device'
    def __init__(self,*reports):self.reports=list(reports);self.commands=[]
    def query(self):
        x=self.reports.pop(0)
        if isinstance(x,Exception):raise x
        return x
    def set_override(self,value):self.commands.append(value)
def detected(version=(1,1,8,5),value=0):return state(Fake(report(value,version)))

class SetupTests(unittest.TestCase):
    def test_auto_trial_from_disabled(self):
        c=Fake(report(),report(15),report(),report(15));r=run_trial(c,reviewed('1.1.8.5'),detected())
        self.assertEqual(c.commands,[True,False,True]);self.assertTrue(r['automatic_readback_passed'])
    def test_auto_trial_from_enabled(self):
        c=Fake(report(15),report(),report(15));r=run_trial(c,reviewed('1.1.8.5'),detected(value=15))
        self.assertEqual(c.commands,[False,True]);self.assertTrue(r['trial_completed'])
    def test_manual_does_not_claim_readback(self):
        v=(1,5,1,1);c=Fake(report(version=v),report(version=v))
        r=run_trial(c,reviewed('1.5.1.1'),detected(v))
        self.assertEqual(c.commands,[True]);self.assertFalse(r['automatic_readback_passed'])
    def test_unknown_or_wrong_state_never_sends(self):
        for raw,p in [(report(version=(9,9,9,9)),None),(report(model=11),reviewed('1.1.8.5')),
                      (report(mode=3),reviewed('1.1.8.5')),(report(rim=1),reviewed('1.1.8.5'))]:
            c=Fake(raw)
            with self.assertRaises(RuntimeError):run_trial(c,p,detected())
            self.assertEqual(c.commands,[])
    def test_changed_device_never_sends(self):
        c=Fake(report());c.identity='different-device'
        with self.assertRaises(RuntimeError):run_trial(c,reviewed('1.1.8.5'),detected())
        self.assertEqual(c.commands,[])
    def test_failed_readback_disables(self):
        c=Fake(report(),report(),report())
        with self.assertRaisesRegex(RuntimeError,'disabled state was confirmed'):run_trial(c,reviewed('1.1.8.5'),detected())
        self.assertEqual(c.commands,[True,False])
    def test_disconnected_cleanup_not_reported_as_success(self):
        c=Fake(report(),RuntimeError('lost USB'),RuntimeError('lost USB'))
        with self.assertRaisesRegex(RuntimeError,'Power off'):run_trial(c,reviewed('1.1.8.5'),detected())
    def test_confirmation_is_required_before_saving(self):
        c=Fake(report(),report(15),report(),report(15));r=run_trial(c,reviewed('1.1.8.5'),detected())
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):save_configuration(tmp,r,detected(value=15),False)
            self.assertFalse((Path(tmp)/'Enable.cmd').exists())
            save_configuration(tmp,r,detected(value=15),True)
            self.assertIn('%~dp0CSL-DD-No-Rim.exe',(Path(tmp)/'Enable.cmd').read_text())
            fresh=Fake(report(15));self.assertIn('Already enabled',enable_saved(fresh,tmp));self.assertEqual(fresh.commands,[])
    def test_firmware_change_invalidates_saved_setup(self):
        c=Fake(report(),report(15),report(),report(15));r=run_trial(c,reviewed('1.1.8.5'),detected())
        with tempfile.TemporaryDirectory() as tmp:
            save_configuration(tmp,r,detected(value=15),True)
            other=Fake(report(version=(1,5,1,1)))
            with self.assertRaises(RuntimeError):enable_saved(other,tmp)
            self.assertEqual(other.commands,[])
    def test_no_saved_profile_blocks_enable(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Fake(report())
            with self.assertRaises(RuntimeError):enable_saved(c,tmp)
            self.assertEqual(c.commands,[])
    def test_save_rechecks_live_state(self):
        c=Fake(report(),report(15),report(),report(15));r=run_trial(c,reviewed('1.1.8.5'),detected())
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):save_configuration(tmp,r,detected(),True)
            self.assertFalse((Path(tmp)/'setup-profile.json').exists())
    def test_manual_stop_wording(self):
        v=(1,5,1,1);c=Fake(report(version=v),report(version=v))
        self.assertIn('does not report',stop_trial(c,reviewed('1.5.1.1'),detected(v)))
        self.assertEqual(c.commands,[False])
    def test_exact_override_reports(self):
        from transport import Connection
        c=Connection.__new__(Connection);c.output={'path':'fake'}
        with patch.object(c,'_write') as writer:
            c.set_override(True);writer.assert_called_with('fake',bytes.fromhex('01fac70000000000'))
            c.set_override(False);writer.assert_called_with('fake',bytes.fromhex('01fa000000000000'))

if __name__=='__main__':unittest.main()

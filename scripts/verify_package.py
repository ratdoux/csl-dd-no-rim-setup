# SPDX-License-Identifier: AGPL-3.0-only
"""Check a generated distribution; never query a base or send an override."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile

BUNDLE_NAME = 'CSL-DD-No-Rim-Setup-Portable'
REQUIRED = {
    'CSL-DD-No-Rim.exe', 'CSL-DD-No-Rim-Setup.exe', '_internal/catalog.json',
    'Setup.cmd', 'Status.cmd', 'Disable.cmd', 'LICENSE.txt', 'README.txt',
    'BUILD-INFO.json', 'SHA256SUMS.txt', 'source/src/setup.spec',
    'source/src/launcher.py', 'source/src/wizard.py', 'source/src/desktop.py',
    'source/src/version.py', 'source/src/test_wizard.py', 'source/src/test_desktop.py',
    'source/scripts/build.py',
    'source/scripts/verify_package.py', 'source/requirements-build.txt',
    'source/VALIDATION.md', 'source/CHANGELOG.md',
    'licenses/Python-LICENSE.txt', 'licenses/PyInstaller-COPYING.txt',
    'licenses/tcl8.6-license.terms', 'licenses/tk8.6-license.terms',
}


def verify_package(path):
    path = Path(path).resolve()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError('Duplicate ZIP entries.')
        for name in names:
            parts = PurePosixPath(name).parts
            if (not parts or parts[0] != BUNDLE_NAME or '..' in parts
                    or '\\' in name or ':' in name or name.startswith('/')):
                raise RuntimeError('Unexpected ZIP path: ' + name)
            if parts[-1].lower() in {'setup-profile.json', 'enable.cmd'}:
                raise RuntimeError('Package contains a pre-confirmed local configuration.')
            if PurePosixPath(name).suffix.lower() in {'.hex', '.bin'}:
                raise RuntimeError('Firmware binaries must not be distributed: ' + name)
        relative = {name[len(BUNDLE_NAME) + 1:] for name in names if not name.endswith('/')}
        if not REQUIRED <= relative:
            raise RuntimeError('Missing package files: ' + repr(sorted(REQUIRED - relative)))
        if not any(name.startswith('_internal/_tcl_data/') for name in relative):
            raise RuntimeError('Tcl runtime data is missing.')
        if not any(name.startswith('_internal/_tk_data/') for name in relative):
            raise RuntimeError('Tk runtime data is missing.')
        if archive.testzip() is not None:
            raise RuntimeError('ZIP CRC verification failed.')
        # All archive paths were checked before extracting to this new temp folder.
        with tempfile.TemporaryDirectory(prefix='csl-dd-package-check-') as tmp:
            archive.extractall(tmp)
            folder = Path(tmp) / BUNDLE_NAME
            checked = set()
            for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
                expected, name = line.split('  ', 1)
                if name not in relative or name in checked:
                    raise RuntimeError('Invalid checksum entry: ' + name)
                actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
                if actual != expected:
                    raise RuntimeError('Checksum mismatch: ' + name)
                checked.add(name)
            if checked != relative - {'SHA256SUMS.txt'}:
                raise RuntimeError('Checksum manifest does not cover every packaged file.')
            info = json.loads((folder / 'BUILD-INFO.json').read_text(encoding='utf-8'))
            env = os.environ.copy()
            env['PATH'] = str(Path(env.get('SystemRoot', 'C:/Windows')) / 'System32')
            env['PYTHONHOME'] = str(Path(tmp) / 'no-external-python')
            env['PYTHONPATH'] = env['PYTHONHOME']
            exe = folder / 'CSL-DD-No-Rim.exe'
            def run(*args):
                return subprocess.run([str(exe), *args], cwd=tmp, env=env, check=True,
                                      capture_output=True, text=True, timeout=30).stdout.strip()
            version = run('--version')
            if version != 'CSL DD No-Rim Setup ' + info['version']:
                raise RuntimeError('Executable version does not match build metadata.')
            ui = json.loads(run('check-ui'))
            if not all(ui.get(k) for k in ('gui_initialized', 'test_disabled', 'confirmation_disabled', 'shortcut_button_present')):
                raise RuntimeError('Packaged GUI initialization or initial state check failed: ' + repr(ui))
            return {'files_checked': len(checked), 'version': version, 'gui': ui,
                    'relocated_without_external_python': True, 'hardware_accessed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_package(args.archive), indent=2))

# SPDX-License-Identifier: AGPL-3.0-only
"""Build and verify the portable Windows app without communicating with hardware."""
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

from verify_package import verify_package

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_NAME = 'CSL-DD-No-Rim-Setup-Portable'
ARCHIVE_NAME = 'CSL-DD-No-Rim-Setup-Windows-x64.zip'
FORBIDDEN = {'setup-profile.json', 'enable.cmd'}
ROOT_SOURCE = (
    'README.md', 'USER-GUIDE.txt', 'VALIDATION.md', 'CHANGELOG.md', 'LICENSE.txt', 'requirements-build.txt',
    'Build.cmd', '.python-version', '.gitignore', '.gitattributes',
)


def run(*args, **kwargs):
    print('+ ' + ' '.join(str(a) for a in args), flush=True)
    return subprocess.run([str(a) for a in args], cwd=ROOT, check=True, **kwargs)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_source(destination):
    files = [ROOT / name for name in ROOT_SOURCE]
    for name in ('src', 'scripts', 'licenses', '.github'):
        for path in (ROOT / name).rglob('*'):
            if '__pycache__' in path.parts or not path.is_file():
                continue
            if path.name.lower() in FORBIDDEN:
                raise RuntimeError('A local device configuration cannot be packaged: ' + str(path))
            if path.suffix not in {'.py', '.json', '.spec', '.txt', '.md', '.terms', '.yml'}:
                raise RuntimeError('Unexpected source file; review before packaging: ' + str(path))
            files.append(path)
    for path in files:
        target = destination / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def copy_licenses(stage):
    target = stage / 'licenses'
    shutil.copytree(ROOT / 'licenses', target)
    python_root = Path(sys.base_prefix)
    shutil.copy2(python_root / 'LICENSE.txt', target / 'Python-LICENSE.txt')
    dist = metadata.distribution('pyinstaller')
    copying = next((p for p in dist.files or [] if str(p).endswith('/licenses/COPYING.txt')), None)
    if copying is None:
        raise RuntimeError('Could not locate the installed PyInstaller license.')
    shutil.copy2(dist.locate_file(copying), target / 'PyInstaller-COPYING.txt')
    for family in ('tcl8.6', 'tk8.6'):
        notice = python_root / 'tcl' / family / 'license.terms'
        if notice.is_file():
            shutil.copy2(notice, target / (family + '-license.terms'))
    shutil.copy2(ROOT / 'LICENSE.txt', stage / 'LICENSE.txt')


def launchers(stage):
    scripts = {'Setup': ['@echo off', 'setlocal', 'start "" "%~dp0CSL-DD-No-Rim-Setup.exe"']}
    for name, action in (('Status', 'status'), ('Disable', 'disable')):
        scripts[name] = [
            '@echo off', 'setlocal', 'title CSL DD - ' + name,
            '"%~dp0CSL-DD-No-Rim.exe" ' + action, 'set "CSL_EXIT=%ERRORLEVEL%"',
            'echo.', 'pause', 'exit /b %CSL_EXIT%',
        ]
    for name, lines in scripts.items():
        (stage / (name + '.cmd')).write_bytes(('\r\n'.join(lines) + '\r\n').encode('ascii'))


def git_info():
    def git(*args):
        result = subprocess.run(['git', *args], cwd=ROOT, check=True,
                                capture_output=True, text=True)
        return result.stdout.strip()
    try:
        return {'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain'))}
    except (OSError, subprocess.CalledProcessError):
        return {'commit': None, 'dirty': None}


def package(bundle, source_ui):
    release = ROOT / 'release'
    release.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='package-', dir=ROOT / 'build') as tmp:
        stage = Path(tmp) / BUNDLE_NAME
        shutil.copytree(bundle, stage)
        copy_source(stage / 'source')
        copy_licenses(stage)
        launchers(stage)
        shutil.copy2(ROOT / 'USER-GUIDE.txt', stage / 'README.txt')
        version = re.search(r"version='CSL DD No-Rim Setup ([^']+)'",
                            (ROOT / 'src/launcher.py').read_text(encoding='utf-8')).group(1)
        info = {
            'version': version, 'built_at_utc': datetime.now(timezone.utc).isoformat(),
            'target': 'Windows x64', 'python': platform.python_version(),
            'tcl': source_ui['tcl'], 'pyinstaller': metadata.version('pyinstaller'),
            'pyinstaller_hooks': metadata.version('pyinstaller-hooks-contrib'),
            'git': git_info(), 'hardware_commands_during_build': False,
            'checks': ['fake-device unit tests', 'source Tk initialization',
                       'relocated ZIP checksum, CLI and Tk verification'],
        }
        (stage / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
        files = sorted(path for path in stage.rglob('*') if path.is_file())
        if any(path.name.lower() in FORBIDDEN for path in files):
            raise RuntimeError('Refusing to ship a pre-confirmed device configuration.')
        manifest = ''.join(sha256(p) + '  ' + p.relative_to(stage).as_posix() + '\n' for p in files)
        (stage / 'SHA256SUMS.txt').write_text(manifest, encoding='utf-8')
        pending = Path(tmp) / ARCHIVE_NAME
        with zipfile.ZipFile(pending, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(Path(tmp)).as_posix())
        # Publish outputs only after the newly created archive passes verification.
        verification = verify_package(pending)
        archive_path = release / ARCHIVE_NAME
        shutil.copy2(pending, archive_path)
        shutil.copy2(stage / 'BUILD-INFO.json', release / 'BUILD-INFO.json')
        (release / (ARCHIVE_NAME + '.sha256')).write_text(
            sha256(archive_path) + '  ' + ARCHIVE_NAME + '\n', encoding='ascii')
        print(json.dumps({'archive': str(archive_path), 'verification': verification}, indent=2))


def main():
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise RuntimeError('Build on Windows with 64-bit Python and Tcl/Tk installed.')
    bundle = ROOT / 'dist' / BUNDLE_NAME
    if bundle.exists() and any(p.name.lower() in FORBIDDEN for p in bundle.rglob('*')):
        raise RuntimeError('The dist folder contains local settings. Move the used app elsewhere before rebuilding.')
    os.environ['PYINSTALLER_CONFIG_DIR'] = str(ROOT / '.pyinstaller-cache')
    run(sys.executable, '-m', 'unittest', 'discover', '-s', 'src', '-p', 'test_*.py', '-v')
    ui = json.loads(run(sys.executable, 'src/launcher.py', 'check-ui',
                        capture_output=True, text=True).stdout)
    if not all(ui.get(k) for k in ('gui_initialized', 'test_disabled', 'confirmation_disabled')):
        raise RuntimeError('Source GUI initialization or initial button states failed: ' + repr(ui))
    run(sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
        '--distpath', ROOT / 'dist', '--workpath', ROOT / 'build', ROOT / 'src/setup.spec')
    package(bundle, ui)


if __name__ == '__main__':
    main()

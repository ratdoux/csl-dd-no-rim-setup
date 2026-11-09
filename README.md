# CSL DD No-Rim Setup

A Windows setup utility for using the CSL DD's existing no-rim force-feedback
command. It detects the base, checks a reviewed firmware profile, runs a
user-requested trial, and creates `Enable.cmd` after the user confirms that FFB
works in a game. The command changes wheelbase RAM; it does not flash firmware.

## Using the app

Extract the **entire** portable ZIP to a writable folder and open `Setup.cmd`.
Connect one CSL DD in yellow PC compatibility mode. The normal Fanatec drivers
are still needed for gaming; Python is bundled in the download.

Follow the setup steps, test with low-strength FFB in a game, then select
**It worked - create launcher**. Use the resulting `Enable.cmd` after restarting
the base. `Status.cmd` reads status and `Disable.cmd` sends the disable command.
See [USER-GUIDE.txt](USER-GUIDE.txt) for the complete procedure and limitations.

| Firmware | Verification available |
| --- | --- |
| 1.1.8.5 | Reviewed and tested on a CSL DD with an 8 Nm supply. Setup checks a reversible status transition and requires game confirmation. |
| 1.5.1.1 | Command reviewed offline. No reliable override flag readback; a manual game trial is required. Not hardware-tested by this project. |
| Other versions | Blocked until their command and status behavior have been reviewed. |

The current profiles require base type 10, status profile 7, compatibility mode,
and no detected rim. Other models, modes, and status profiles are unsupported.
The app can inspect a matching local firmware image, but cannot dump the device's
flash. A version-based fallback is shown explicitly when no matching image is
available. Matching a short byte pattern alone never authorizes a command.

## Build on Windows x64

The checked build environment is Python **3.10.9 x64**, including Tcl/Tk, and the
pinned dependencies in [requirements-build.txt](requirements-build.txt).
With that Python installed, double-click `Build.cmd`, or run in PowerShell:

```powershell
py -3.10 -m venv .build-env
.\.build-env\Scripts\python.exe -m pip install -r requirements-build.txt
.\.build-env\Scripts\python.exe scripts/build.py
```

The build runs the fake-device unit tests, checks Tk initialization, builds both
executables with PyInstaller, packages source and license notices, and verifies
the ZIP after extracting it to a new location. The extracted CLI and GUI checks
run with Python removed from `PATH` and invalid `PYTHONHOME`/`PYTHONPATH` values.
No build or CI step opens a wheelbase connection or sends a motor command.

Outputs:

- `release/CSL-DD-No-Rim-Setup-Windows-x64.zip`
- `release/CSL-DD-No-Rim-Setup-Windows-x64.zip.sha256`
- `release/BUILD-INFO.json` with actual runtime versions and Git revision

The ZIP includes the complete source and build scripts under `source/`.
It never contains a pre-confirmed `setup-profile.json` or `Enable.cmd`.
Build directories, runtime binaries, firmware images, and local settings are
excluded from Git. A generated ZIP can be checked again with:

```powershell
.\.build-env\Scripts\python.exe scripts/verify_package.py release/CSL-DD-No-Rim-Setup-Windows-x64.zip
```

## GitHub Actions

[The Windows workflow](.github/workflows/build-windows.yml) runs on pushes, pull
requests, and manual dispatch. It uses the same build script, with dependencies
pinned and GitHub actions pinned to reviewed release commits. Successful runs
attach the portable ZIP, checksum, and build metadata as a downloadable artifact
for 30 days. It does not publish a GitHub Release.

Push this repository to GitHub to run the workflow there. Local verification
does not establish that a hosted Actions run has succeeded.

## Development

```powershell
.\.build-env\Scripts\python.exe -m unittest discover -s src -p "test_*.py" -v
.\.build-env\Scripts\python.exe src/launcher.py setup
```

`src/engine.py` owns the trial and confirmation state; `src/transport.py` owns
the fixed HID reports; `src/catalog.json` contains the reviewed firmware
profiles. Adding a firmware version requires reviewing its handler, disable
semantics, output gate, and status layout, followed by hardware validation.
Do not infer compatibility from the firmware number or a short pattern match.

## License and attribution

AGPL-3.0-only; see [LICENSE.txt](LICENSE.txt). Firmware decryption is adapted from
[ProjectSerotonin/vlfx](https://github.com/ProjectSerotonin/vlfx/blob/f9b97cbf974d870d83392a71a66ca8663987e1e8/src/fanatec_decrypt.rs).
Earlier utility components retain their MIT notice. Python, Tcl/Tk, and
PyInstaller notices are included in portable builds; see [licenses/README.md](licenses/README.md).
No Fanatec firmware images or vendor SDK DLLs are distributed. This is an
independent project, not an official Fanatec application.

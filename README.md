# CSL DD No-Rim Setup

A Windows setup utility for using the CSL DD's existing no-rim force-feedback
command. It detects the base, checks a reviewed firmware profile, runs a
user-requested trial, and creates `Enable.cmd` after the user confirms that FFB
works in a game. The command changes wheelbase RAM; it does not flash firmware.

## Using the app

Extract the **entire** portable ZIP to a writable folder and open `Setup.cmd`.
Connect one CSL DD in yellow PC compatibility mode. The normal Fanatec drivers
are still needed for gaming; Python is bundled in the download.

The GUI checks the connected base and firmware automatically. When it is ready,
check the readiness box and click **Enable FFB**. Test with low-strength FFB in
a game, then click **FFB works - save setup** to create `Enable.cmd`.

Click **Add desktop shortcut** to put **Enable CSL DD FFB** on your Windows
Desktop. Use that shortcut or `Enable.cmd` before starting your game after
restarting the base. Keep the extracted app folder in place; the shortcut points
to it. The GUI also recognizes your saved setup and can enable it directly.
**Show technical details** contains firmware-image inspection and review notes.
`Status.cmd` reads status and `Disable.cmd` sends the disable command.
See [USER-GUIDE.txt](USER-GUIDE.txt) for the complete procedure and limitations.

> **Firmware compatibility disclaimer:** No-rim FFB has been confirmed on
> **1.1.8.5 and 1.5.1.1**, using the same CSL DD with an 8 Nm supply in yellow PC
> compatibility mode. This is validation on one base, not every setup. It is
> expected to work on other CSL DD firmware implementing the same command with the
> same parameters and behavior, but this has not been verified on other
> versions and is not guaranteed. Status reporting can differ between versions.
> The app still blocks unreviewed firmware until a compatible profile is added;
> the command's presence alone does not establish full app compatibility.

| Firmware | Verification available |
| --- | --- |
| 1.1.8.5 | Reviewed and tested on a CSL DD with an 8 Nm supply. Setup checks a reversible status transition and requires game confirmation. |
| 1.5.1.1 | Reviewed; standalone FFB and subsequent game FFB confirmed on the same base on 2026-11-09. No reliable override flag readback; each user must still confirm their own game trial. |
| Other versions | Blocked until their command and status behavior have been reviewed. |

The current profiles require base type 10, status profile 7, compatibility mode,
and no detected rim. Other models, modes, and status profiles are unsupported.
The app can inspect a matching local firmware image, but cannot dump the device's
flash. A version-based fallback is shown explicitly when no matching image is
available. Matching a short byte pattern alone never authorizes a command.

On 1.5.1.1, the initial game attempt had no FFB; a standalone test and a later
game attempt worked. The reason for that difference has not been isolated,
and a fresh power-cycle retest has not been completed. The application sends
the existing override command; it does not automatically run a force pulse.
See [VALIDATION.md](VALIDATION.md) for the observed results and their limits.

Version 2.1.0 adds the guided interface and desktop shortcut creation. Saved
profiles from 2.0.1 remain compatible. Version 2.0.1 changed the 1.5.1.1 review
record; profiles for that firmware from 2.0.0 still need Setup again.

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
for 30 days.

Pushing a version tag such as `v2.1.1` also creates a **published GitHub Release**
after the build and verification succeed. The release includes the portable ZIP,
its SHA-256 checksum, build metadata, and automatically generated release notes.
Rerunning a tag's workflow updates its existing release assets. Tags containing
a hyphen, such as `v2.1.0-rc.1`, are marked as prereleases.

The tag must be `v` followed by the app version in `src/version.py`; a mismatch
stops publication. For the current version, after committing the changes and
configuring the GitHub remote:

```powershell
git tag v2.1.1
git push origin v2.1.1
```

Branch pushes, pull requests, and manual runs only produce build artifacts.
Release publication runs in a separate job with `contents: write`; the build
job retains read-only repository access.

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

`src/wizard.py` provides the GUI. `src/desktop.py` creates a native Windows
shortcut using Shell APIs, including redirected/OneDrive Desktops. Shortcut
creation does not execute the launcher or connect to hardware. Tests cover GUI
command gating with fake devices and actual Shell links in temporary folders.

## License and attribution

AGPL-3.0-only; see [LICENSE.txt](LICENSE.txt). Firmware decryption is adapted from
[ProjectSerotonin/vlfx](https://github.com/ProjectSerotonin/vlfx/blob/f9b97cbf974d870d83392a71a66ca8663987e1e8/src/fanatec_decrypt.rs).
Earlier utility components retain their MIT notice. Python, Tcl/Tk, and
PyInstaller notices are included in portable builds; see [licenses/README.md](licenses/README.md).
No Fanatec firmware images or vendor SDK DLLs are distributed. This is an
independent project, not an official Fanatec application.

# Third-party notices

- `Previous-utility-MIT.txt`: notice retained for the earlier utility components.
- `tcl8.6-license.terms`: Tcl notice from the upstream
  [8.6.12 source](https://github.com/tcltk/tcl/blob/core-8-6-12/license.terms).
- `tk8.6-license.terms`: Tk notice from the Python 3.10.9 installation used for
  the initial build.

The build copies the actual Python runtime's `LICENSE.txt` and the installed
PyInstaller distribution's `COPYING.txt` into the portable package. Tcl/Tk
notices are taken from the build's Python installation when available, with
the included 8.6 notices as fallbacks. Review these notices when changing the
bundled runtime family. The corresponding Python license includes additional
bundled-component notices.

The application's firmware decryption implementation is adapted from
[ProjectSerotonin/vlfx](https://github.com/ProjectSerotonin/vlfx/blob/f9b97cbf974d870d83392a71a66ca8663987e1e8/src/fanatec_decrypt.rs),
licensed under AGPL-3.0. The complete application source and AGPL license are
included in every portable package.

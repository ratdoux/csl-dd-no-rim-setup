# Changelog

## 2.1.1 — 2026-11-09

- Compare shortcut targets by file identity in tests, so Windows short folder
  aliases on GitHub runners are accepted alongside their full paths.
- Clarify the readiness-box prompt in the GUI footer.

The 2.1.0 tag's release build was blocked by the path-comparison tests; 2.1.1
contains the same GUI and shortcut features with that build check corrected.

## 2.1.0 — 2026-11-09

- Guide users through automatic base/firmware checks, Enable FFB, and game
  confirmation in a simpler GUI, with optional technical details.
- Recognize saved setups for daily enabling directly from the GUI.
- Add a native desktop shortcut to the confirmed Enable.cmd, respecting
  redirected Desktops and preserving unrelated existing shortcuts.
- Add GUI state and native shortcut tests; bundle both features in the portable
  app without new dependencies. Existing 2.0.1 saved setups remain compatible.

Detection and shortcut creation send no enable command. The reviewed firmware
profiles, override reports and game-confirmation requirement are unchanged.

## 2.0.1 — 2026-11-09

- Record successful standalone and in-game no-rim FFB on CSL DD firmware 1.5.1.1.
- Document the scope and limitations of tests on 1.1.8.5 and 1.5.1.1.
- Show the hardware validation note in Setup while retaining individual game
  confirmation and the manual status strategy for 1.5.1.1.
- Include validation notes in portable builds and cover saving/enabling a
  game-confirmed manual profile with a zero availability value.

The override command, unknown-firmware block, and absence of automatic force
effects are unchanged. Existing 1.5.1.1 saved profiles need Setup again because
the reviewed profile fingerprint changed.

## 2.0.0

Initial setup wizard, reviewed firmware catalog, local portable build, and
GitHub Actions build/release workflow.

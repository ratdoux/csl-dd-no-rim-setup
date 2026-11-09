# Changelog

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

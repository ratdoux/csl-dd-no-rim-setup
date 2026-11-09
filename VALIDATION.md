# Firmware validation

These results describe one physical CSL DD with an 8 Nm supply, in yellow PC
compatibility mode (USB VID `0EB7`, PID `0004`), base type 10, status profile 7,
and rim ID 0. They do not establish support for other bases, modes, power supplies,
or firmware versions. No firmware was patched or flashed by this application.

## Firmware 1.1.8.5

The command handler and force-output gate were reviewed. The no-rim enable and
disable commands produced reversible availability transitions between 0 and 15,
and the operator confirmed force feedback in a game. This profile uses automatic
status readback followed by each user's game confirmation.

## Firmware 1.5.1.1 — 2026-11-09

The connected base reported 1.5.1.1. A matching installed firmware image passed
the catalog's full-image hash and instruction-block checks. This is verification
of a local image, not a readback of the device's flash.

The existing no-rim enable command is `01 FA C7 00 00 00 00 00`. The reviewed
disable command is `01 FA 00 00 00 00 00 00`. The command's behavior is unchanged
in this release; only the recorded validation and user-facing documentation change.

Observed sequence:

1. The enable write and subsequent status request completed, but the operator's
   first game attempt had steering and no force feedback.
2. A 5% / 0.2-second standalone test was inconclusive; the operator may have
   moved the wheel. It is not counted as a successful force test.
3. Explicitly requested 20% / 1-second DirectInput tests completed. The final
   test had stable steering readings beforehand, changing readings during the
   pulse, and explicit operator confirmation that the wheel moved by itself.
   Effect-stop, unload, and stop-all calls succeeded; temporary DirectInput
   gain and autocenter settings were restored.
4. The operator then confirmed force feedback working in the game.

The standalone diagnostic acquired the DirectInput device before sending the
reviewed override command and creating the finite force effect. The reason the
initial game attempt failed while the later attempt worked was not isolated.
No claim is made that a pulse is required, or that the current launcher has been
validated from a fresh power cycle on this firmware. The diagnostic pulse is
not part of Setup, the daily enable launcher, or CI.

This firmware's examined system-report calculation does not expose the override
flag. Availability byte 55 must not be interpreted as the 1.1.8.5 acknowledgement.
DirectInput also returned contradictory state flags, so those flags were not
used as proof of physical output. The profile remains `readback: manual` and
requires the user's own game confirmation.

## Limits

Hardware validation is distinct from unit tests and packaging checks. The
successful 1.5.1.1 result does not establish USB reconnect behavior, repeatability
after a fresh base power cycle, or identical behavior on another person's base.
Unknown firmware remains blocked pending review. Raw device paths, personal
profiles, firmware images, and diagnostic logs are not distributed with this repo.

# Contributing

The most useful contribution is a measurement on a gauge this project has not
seen. Different needle colour, different dial size, different manufacturer. If
the method holds across gauges, everything after it is calibration.

## Sending a measurement

1. Build the fixture, see [`hardware/jig/README.md`](hardware/jig/README.md)
2. Generate cards for your gauge:
   `python3 tools/make_cards.py --dial 25 --max 30 --sweep 270 --scale 2`
3. Run the series as described in [`docs/method/measurement.md`](docs/method/measurement.md)
4. Open an issue with the text record from `docs/log/data/`, and say which
   gauge, which sensor, which light and which aperture

Negative results are wanted as much as positive ones. A gauge where this does
not work is worth more to the project than a third one where it does.

## Sending code or hardware

Pull requests are welcome. Two house rules, both there for a reason:

- **Measurements over opinions.** A change to the optics, the geometry or the
  evaluation comes with the numbers that justify it.
- **Failures stay in the log.** `docs/log/` keeps the versions that were thrown
  away and why. Do not tidy them out. They are the part of this repository that
  saves the next person a weekend.

Code, comments and documentation are in English.

## Contributor agreement

By opening a pull request you confirm:

1. The work is yours, or you have the right to submit it.
2. You licence it to this project under the licence of the directory it lands
   in, as listed in [`LICENSE.md`](LICENSE.md).
3. You grant the project owner the additional right to release your
   contribution under other licence terms, including commercial ones.

Point 3 exists so that a finished product can be built on this work later
without having to track down every contributor. It does not take anything away
from you: your contribution stays available to everyone under the open licence,
permanently and irrevocably.

If that is not acceptable to you, say so in the pull request. A contribution
under the open licence alone is still welcome, it will simply be kept where the
distinction matters.

This is the project's own wording and not legal advice. Anyone relying on it
commercially should have a lawyer confirm it.

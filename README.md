# halo-gauge-experiment

Open research: optical, non-contact needle readout for 20 mm analog pressure gauges, tested on the Huben GK1.

The gauge on a pre-charged pneumatic airgun sits inside a sealed, type-approved pressure system. Replacing it with an electronic transducer is neither legally nor technically an option for the end user. This project reads the existing needle from the outside, through the glass, with a ring of reflective light sensors, and turns the gauge into a digital data source without touching the pressure system.

## Status

Experiment phase. A 3D printed test jig (version 5) holds a TCS34725 color sensor and two ALS-PT19 phototransistors over printed test cards. The first measurement series answers one question: is the optical contrast between the white dial and the yellow needle good enough for a cheap reflective sensor. Go / no-go threshold is SNR >= 10.

Results are published here as they are measured, including the ones that fail.

## Repository layout

```
docs/research/    prior art, patents, related projects
docs/method/      measurement method, test cards, evaluation
docs/log/         chronological build log, including discarded versions
hardware/jig/     printable test jig, STL files, bill of materials, print settings
hardware/cards/   test card artwork (dial and needle, 1:1)
firmware/probe/   Arduino sketch for the measurement rig
briefings/        work orders for the implementation assistant
```

## Reproducing the experiment

1. Print the jig, see `hardware/jig/README.md` for parts, orientation and settings.
2. Print the test cards from `hardware/cards/`, 100 x 100 mm.
3. Wire the Heltec WiFi LoRa 32 V2 as described in `docs/method/measurement.md`.
4. Flash `firmware/probe/halo_gauge_probe.ino`.
5. Run the series, paste the serial output into an issue or a pull request.

If you have a different gauge, any dial size, any needle color, a measurement with your gauge is the most useful contribution this project can get.

## Prior art

This is not the first optical gauge reader. Reflective sensor rings over pointer instruments are documented since 2006, Siemens holds an active patent on a specific triangular sensor geometry, and camera based readers exist commercially and as open source. The differences, and the reasons this project exists anyway, are documented in `docs/research/prior-art.md`.

## Origin

This project started inside the CYB3RGUN development at CYB3RGUN and is published as a standalone community project.

## Trademarks

Huben and GK1 are trademarks of their respective owner. This project is not affiliated with or endorsed by Huben.

## License

The repository is private during the experiment phase. With the first public release the following licenses are added: GPL-3.0 for firmware, CERN-OHL-S-2.0 for hardware, CC BY-SA 4.0 for documentation. Contributions will require a contributor license agreement, see `CONTRIBUTING.md` once published.

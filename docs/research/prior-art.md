# Prior art

Last reviewed: 2026-09-09. This page is a technical review, not legal advice.

## Summary

Reading a pointer instrument optically from the outside is an old idea. Three families exist:

1. Reflective sensor rings: several light sensors on an arc above the dial, the pointer shades some of them. Documented since 2006, refined and patented by Siemens in 2019.
2. Camera based readers: image the dial, find the needle by image processing. Commercial since 2008, open source since 2020.
3. Mechanical or magnetic retrofits: magnet on the Bourdon tube with a Hall sensor, or replacing the gauge with a transducer. Invasive, not applicable to a sealed, type-approved pressure system.

This project belongs to family 1. It does not claim to have invented the sensor ring. What it adds is listed at the end.

## Patents

### Siemens AG, US 12,044,549 B2 and DE 10 2019 207 322 B4

Title: Optical reading device for a pointer instrument. Inventors: Ralf Huck, Stefan Klehr. Priority 2019-05-20 (DE 10 2019 207 322.0). US grant 2024-07-23, active until 2040-10-31. German family member granted 2021-07-29, active.

https://patents.google.com/patent/US12044549B2/en
https://patents.google.com/patent/DE102019207322B4/en

Claim 1 (US):

> An optical reading device of a pointer instrument having a pointer and a scale face or dial with different reflection properties, comprising: an illumination apparatus for illuminating the scale face or dial of the pointer instrument; and a plurality of triangular light sensor elements which are arranged in a circle about a rotation axis of the pointer for capturing light of the illumination apparatus reflected back by the scale face or dial of the pointer instrument; wherein the illumination apparatus is configured to evenly illuminate the scale face or dial at least in a region opposite the circle; and wherein the plurality of triangular light sensor elements each substantially formed as isosceles triangles and are each arranged adjacent to one another along a circumferential direction of the circle.

The inventive core is the triangular element shape. Because adjacent isosceles triangles are offset by half their base width, the pointer always shades two neighbours at once and the ratio of the two shadings gives a continuous position. Dependent claims cover 180 degree alternation, abutting limbs, triangular light guides made of transparent plastic, and ambient light collection.

Relevance to this project: the sensor elements here are rectangular SMD phototransistors (0603) behind printed baffles. They are not triangular and not arranged as abutting isosceles triangles. As read by the authors, claim 1 is therefore not met. Design rule derived from this: no triangular sensor elements, no triangular light guides. A freedom-to-operate opinion by a patent attorney is planned before any commercial sale, with DE 10 2019 207 322 B4 as the primary reference.

Technical lessons taken from the description: switch the LED on only for the duration of a reading; use an ambient light sensor to skip the LED when daylight suffices; uniform illumination of the sensed arc is essential and Siemens uses an annular light guide for it.

### BAM, WO 2007/147609 A2

Bundesanstalt fuer Materialforschung und -pruefung. Monitoring device for a measuring device. Priority June 2006.

https://patents.google.com/patent/WO2007147609A2/en

Describes a light source and a sensor fastened on the glass of a pointer instrument, working as a reflective light barrier that detects when the pointer reaches a predetermined position, and several such units arranged in a ring around the pointer axis to capture the position in segments. Mounting on an acrylic carrier by screws, snap fit or adhesive.

This is the sensor ring in its coarse, segment-wise form and is the closest published ancestor of this project. Any national patents from this application expire in 2027 at the latest. Status to be checked in DEPATISnet before commercial sale.

### Further patents cited by the Siemens examiner

- Rosemount Inc., US 2014/0239151 A1, self-powered optical detector for mechanical gauge instruments (2013).
- Shanghai Fire Research Institute, CN 103234593 A, digitizer for the pointer pressure gauge of an air respirator (2013). Closest application: small gauge on a sealed breathing air system.
- Lipman Science and Technology, US 2008/0048879 A1, automatic monitoring of analog gauges (2004).
- Baumer Bourdon-Haenni, EP 2905595 A1, gauge testing device, camera based (2014).

## Commercial products

### Cypress Envirosystems Wireless Gauge Reader (WGR)

https://cypressenvirosystems.com/products/wireless-gauge-reader-2/

Clip-on reader for existing gauges, on the market since 2008, patented. Reads the needle optically, transmits wirelessly. Gauge diameters 38 to 114 mm, accuracy stated as +/- 1.5 % of full scale. The user manual lists an image capture mode, so the device is camera based.

Lessons: "non-invasive, the pressure system stays sealed" has been the central selling argument of this device class for 17 years. +/- 1.5 % of full scale is the benchmark to beat or match. Dials below 38 mm are not served.

## Open source

### AI-on-the-edge-device

https://github.com/jomjol/AI-on-the-edge-device

ESP32-CAM with TensorFlow Lite, reads water, gas and electricity meters including the small analog pointer dials, everything on the device. Large community, maintained since 2020, commercial boards available.

Why this project does not use a camera: power. The sensor ring needs a few photodiodes and a briefly pulsed LED, which allows battery or energy harvesting operation. A camera plus inference costs orders of magnitude more energy and does not fit a device that lives in a pistol grip.

## What this project adds

1. Spectral contrast optimisation. None of the sources above selects the illumination wavelength for the needle pigment. The Huben GK1 needle is yellow on a white dial. Yellow pigment absorbs blue, so blue illumination (around 470 nm) with a broadband detector maximises the needle to dial contrast. This is the hypothesis the first experiment tests.
2. Dial size. Commercial readers start at 38 mm. This project targets a 20 mm dial with 0603 phototransistors at about 1.3 mm pitch on a 7 mm radius.
3. Application. A type-approved airgun pressure system that must not be modified, read from a battery powered grip.
4. Published method. Test jig, test cards, SNR threshold and raw data are public, including negative results.

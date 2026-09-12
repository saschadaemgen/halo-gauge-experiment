# Measurement method, stage 0 and 1

## Question

Is the reflective contrast between a white dial and a yellow needle large enough for a cheap reflective sensor to detect the needle reliably, and does blue illumination improve it.

Go / no-go: SNR >= 10 on at least one channel, where SNR is the difference between the white and the yellow signal divided by the combined noise.

## Sensors on the rig

- TCS34725 RGB color sensor (CJMCU clone, I2C 0x29). Gives four 16 bit channels: clear, red, green, blue. Used to characterise the contrast per wavelength band.
- Two ALS-PT19 phototransistor breakouts (analog out). Broadband detectors, the same class of part the final sensor ring will use.
- One white and one blue 5 mm LED, clear lens, in the jig's LED holders, aimed at the measurement spot from 20 degrees elevation.

None of these sensors has a defined field of view. Their angular response is Lambertian, effectively 180 degrees. The measurement spot is therefore defined entirely by the pinhole card in the jig, see `hardware/jig/README.md`.

## Wiring, Heltec WiFi LoRa 32 V2

| Part | Pin | Heltec |
|---|---|---|
| TCS34725 | VIN | 5V |
| TCS34725 | GND | GND |
| TCS34725 | SDA | GPIO 4 (shared with OLED) |
| TCS34725 | SCL | GPIO 15 (shared with OLED) |
| TCS34725 | LED | GND (board LED permanently off) |
| ALS-PT19 A | + / - / out | 3V3 / GND / GPIO 36 |
| ALS-PT19 B | + / - / out | 3V3 / GND / GPIO 37 |
| white LED | anode via 220 ohm | GPIO 23 |
| blue LED | anode via 220 ohm | GPIO 22 |

The OLED of the Heltec V2 sits on GPIO 4 / 15 with reset on GPIO 16 and is powered through Vext (GPIO 21 low). The sketch handles this.

## Test cards

All cards are 100 x 100 mm, printed on the same printer and paper, and sit in the pocket of the base plate.

1. Full white.
2. Full yellow in the exact needle colour taken from the gauge artwork.
3. Nine 1:1 dial cards with the needle at 0, 5, 10, 15, 20, 25, 30, 35 and 40 MPa. Dial centre at card centre.

Cards 1 and 2 answer the material question (does the colour contrast exist). The 1:1 cards answer the geometry question (does a 1 mm wide needle still register through a small aperture). Printer ink is not needle lacquer, so the cards prove viability, not calibration. Calibration happens on the real gauge later.

## Procedure

1. Card in the pocket, rail on the pegs, frame and LED holders in the rail window, pins, slide with pinhole card, carrier with sensor board.
2. Serial monitor at 115200 baud. The OLED shows live values. If the clear channel shows `SAT`, lower the gain with `g`.
3. `w` runs the white series: 50 samples with the LED on, 50 with the LED off.
4. Swap to the yellow card, `y` runs the yellow series.
5. `r` prints the report: per channel signal white, signal yellow, contrast, noise, SNR, verdict.
6. `i` switches from the white LED to the blue LED. Repeat 3 to 5.

The differential (LED on minus LED off) removes constant ambient light. It does not remove flicker, so the room lights stay off during a series.

## Evaluation

Per channel:

- signal = mean(on) minus mean(off)
- noise = sqrt(sd(on)^2 + sd(off)^2)
- contrast = (signal_white minus signal_yellow) / signal_white
- SNR = |signal_white minus signal_yellow| / sqrt(noise_white^2 + noise_yellow^2)

Expected under white light: red and green nearly unchanged between white and yellow, blue drops. The broadband phototransistors see little difference.

Expected under blue light: the clear channel and both phototransistors drop on yellow. This is the number that decides the sensor ring, because the ring will use broadband phototransistors under blue LEDs.

## Raw data

Serial output of every series is stored verbatim under `docs/log/data/` with date, card, light source, gain and pinhole diameter in the file name.

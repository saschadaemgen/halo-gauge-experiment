# Test jig V5

Modular, all parts print flat without supports, all bores are vertical in print orientation. See `docs/log/jig-versions.md` for why.

## Printed parts

| File | Qty | Size mm | Print orientation |
|---|---|---|---|
| gauge_jig_base.stl | 1 | 120 x 120 x 4 | as exported, pocket up |
| jig_v5_rail.stl | 1 | 120 x 60 x 4 | flat |
| jig_v5_frame.stl | 1 | 44 x 44 x 14 | flip: the face with the small 24 mm opening goes on the bed |
| jig_v5_slide.stl | 1 | 44 x 44 x 2 | flat, card recess up |
| jig_v5_carrier.stl | 1 | 44 x 44 x 26 | flat, board pocket up |
| jig_v5_led_holder.stl | 2 | 24 x 44 x 22 | as exported, stands on the slanted face, bore vertical |

## Non-printed parts

- 4 pins, 1.75 mm filament, 12 mm long (or 2 mm nails)
- 2 LEDs 5 mm, clear lens, one white and one blue, with 220 ohm series resistors
- black photo card, matte, about 250 g/m2, cut to 28 x 28 mm, hole in the centre: sewing needle for 0.5 to 0.8 mm, pin vise drill for 1.0 and 1.5 mm
- TCS34725 breakout (Adafruit 1334 layout, 20.32 x 20.32 mm), header soldered on the top side so the board lies component side down
- test cards 100 x 100 mm, see `hardware/cards/`

## Assembly

Base plate, test card in the pocket, rail on the four pegs. Frame into the rail window, it stands on the card. One LED holder on each side of the frame in the same window, slanted face outwards, they also stand on the card. Four pins into the frame, slide on top, pinhole card into the recess, carrier on top, sensor board into the pocket component side down, black tape over the pocket. LEDs into the holders from the outside, flange in the counterbore, tape around the LED foot.

## Print settings, Bambu Lab P2S

Layer height 0.20 mm. The card recess in the slide is 0.4 mm deep, that is exactly two layers. Other layer heights round it to a wrong depth.

No supports, no bridging. If the slicer suggests supports the part is oriented wrong.

Material: black PLA. Lowest shrinkage of the common filaments, which matters for a stack of four parts that must fit together. Black because white and clear filament transmit light through the walls.

Walls 4 perimeters, infill 30 % gyroid, seam aligned or rear (check that the seam is not inside the LED bore).

X-Y hole compensation stays at 0. It acts on all holes equally while small holes shrink more than large ones, so no single value fits 1.9, 5.4 and 8 mm at once. Instead: ream the pin holes with a 1.8 mm drill, the LED bore with 5.5 mm only if the LED does not slide in.

Print the slide first. It takes minutes. If the pin fits and the pinhole card sits in the recess, print the rest.

## Geometry

- card surface: 0
- frame chamber: 0 to 12, opening 24 x 24 from 12 to 14
- slide: 14 to 16, pinhole card at about 15.75
- carrier: 16 to 42, chip face at 38.35
- LED axis crosses the frame wall at 8.1 above the card

Spot diameter on the card is about 1.7 x pinhole diameter plus 0.3 mm.

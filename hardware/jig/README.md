# Test fixture V6

A light tight reflectance fixture with a 20/0 geometry, an exchangeable field
stop, and one pocket that takes either sensor. Printed in black PLA, all parts
flat, no supports, every bore vertical in print orientation.

See `docs/log/jig-versions.md` for how it got here and what not to repeat.

## Printed parts

| file | qty | size mm | print orientation |
|---|---|---|---|
| gauge_jig_base.stl | 1 | 120 x 120 x 4 | as exported, pocket up |
| jig_v6_rail.stl | 1 | 120 x 60 x 4 | flat |
| jig_v6_frame.stl | 1 | 46 x 46 x 14 | flipped: the face with the small 24 mm opening on the bed |
| jig_v6_slide.stl | 1 | 46 x 46 x 2 | flat, card recess up |
| jig_v6_carrier.stl | 1 | 46 x 46 x 26 | flat, board pocket up |
| jig_v6_lid_tcs.stl | 1 | 46 x 46 x 2 | flat |
| jig_v6_lid_pt19.stl | 1 | 46 x 46 x 2 | flat |
| jig_v6_led_holder.stl | 2 | 26 x 46 x 22 | as exported, standing on the slanted face |
| jig_v6_led_cap.stl | 2 | 11 x 28 x 3 | flat |
| jig_v6_pt19_insert.stl | 1 | 20.3 x 20.3 x 3.2 | flat, pocket up |
| jig_v5_pinhole_plates.stl | 1 print, four plates | 28 x 28 x 0.4 each | flat |

## Not printed

- M3 x 40, four off, through carrier and slide into the frame
- M3 x 10, four off, two per LED cap
- 2 LEDs, 5 mm, clear lens, one blue around 470 nm and one cold white
- 2 resistors to suit the supply, or an LED lead with one built in
- 2 logic level MOSFETs and 2 resistors of 47 k for the gate pull-down
- black photo card, matte, cut to 28 x 28 mm, hole pierced or drilled in the
  centre. This is the field stop. It does not come out of a printer.
- a TCS34725 breakout on the Adafruit 1334 layout, or an ALS-PT19 on the
  Adafruit 2748 layout. Headers soldered to the top, so the board lies
  component side down.

## Orientation, the part that is easy to get wrong

**Frame:** the open chamber with the two window cutouts goes face down onto the
card. The closed face with the small 24 mm opening and the print texture faces
up. Turn it the other way and the LEDs shine into a wall.

**LED holders:** flat face on the card, slanted face outwards. The LED goes in
from the slanted face, so its light leaves at the vertical inner face and
crosses the window of the frame on its way down to the spot.

**Slide:** recess up, the aperture card drops into it.

**Carrier:** pocket up, the sensor board lies in it component side down.

## Assembly

Card in the pocket, rail on the four pegs, frame in the middle of the rail
window, an LED holder either side of it. Slide on the frame, aperture card in
its recess, carrier on top, four long screws. Sensor board into the pocket, lid
on, done. LEDs in from outside, caps with two short screws each.

## Print settings, Bambu Lab P1S or P2S

Layer height 0.20 mm. The card recess in the slide is 0.4 mm deep, which is
exactly two layers. Another layer height rounds it to the wrong depth.

Black PLA. Lowest shrinkage of the common filaments, which matters for a stack
of parts that has to fit together, and black because white and clear filament
carry light through the walls.

Four perimeters, 30 % gyroid, seam aligned or rear. Check that the seam does
not fall inside the LED bore.

X-Y hole compensation stays at zero. It acts on every hole equally while small
holes shrink more than large ones, so no single value suits 2.5, 5.4 and 8 mm
at once. Ream the M3 tap holes with 2.5 mm and the LED bore with 5.5 mm only if
the LED will not slide in.

Print the slide first. It takes minutes, and if the aperture card sits in its
recess the rest is worth printing.

## Geometry

- card surface: 0
- frame chamber: 0 to 12, opening 24 x 24 from 12 to 14
- slide: 14 to 16, aperture card at about 15.75
- carrier: 16 to 42
- LED axis crosses the frame wall at 8.1 above the card, at 20 degrees

Spot diameter on the card is roughly 1.7 times the aperture plus 0.3 mm.

# Test jig, version history

This is the log of how the test jig got to version 5. Versions 1 to 4 were discarded before or during printing. They are documented here because the reasons are the design rules for the final sensor ring.

## V1, 2026-09-08

Base plate 120 x 120 mm with a card pocket, a 120 mm bridge with a board pocket, and five 5 mm aperture discs with printed holes of 0.6 to 3.0 mm. LED channels bored at 28 degrees through the bridge body.

Discarded because:

- The 0.6 mm printed hole did not exist after printing, even at 0.08 mm layer height. FDM cannot produce clean holes below about 1.5 mm.
- The 5 mm discs were too small to handle or to seat repeatably.
- Angled 3 mm bores through a solid body print badly, the top of the bore sags and the LED sits crooked.
- The tunnel under the bridge was open on both long sides. Ambient light entered from the sides and reflected off the white card to the sensor.

## V2 and V3, 2026-09-09

Same bridge with light skirts along both long edges, first with a 0.3 mm gap above the card (V2), then touching the card (V3). Fixed the side leak, not the other three problems. Discarded with V1.

## V4, 2026-09-09

First modular stack: frame, aperture slide, sensor carrier, clamshell LED plugs for 3 mm LEDs, rail. All parts flat, all bores vertical in print orientation, pinhole in a black card instead of a printed hole.

Discarded before printing because the available LEDs are 5 mm, not 3 mm, and the clamshell plug geometry does not scale to a 5 mm body inside the frame.

Lesson: ask for the component dimensions before designing the holder.

## V5, 2026-09-09, current

Modular stack, five printed parts plus the V1 base plate:

- frame 44 x 44 x 14, stands on the card, light chamber 34 x 34 x 12, opening 24 x 24 in the top, light windows 12 x 12 in two walls
- slide 44 x 44 x 2, carries a 28 x 28 mm black pinhole card
- carrier 44 x 44 x 26, holds the TCS34725 board component side down, 20 mm deep 8 mm shaft
- two LED holders for 5 mm LEDs, outside the frame, bore aimed at the spot from 20 degrees, outer face cut perpendicular to the bore so the part prints standing with the bore vertical
- rail 120 x 60 x 4, locates frame and holders on the base plate pegs

Four pins of 1.75 mm filament align frame, slide and carrier.

Geometry: aperture 15.75 mm above the card, chip 22.6 mm above the aperture. Spot on the card is about 1.7 x pinhole diameter plus 0.3 mm: a 0.5 mm needle hole gives 1.1 mm, a 1.0 mm drilled hole gives 2.0 mm.

Design rules that came out of V1 to V4 and carry over to the sensor ring PCB and its baffles:

1. Every printed bore is vertical in its print orientation.
2. No printed hole below 1.5 mm. Small apertures go into black card, pierced or drilled.
3. Any part that must be handled is at least 20 mm across.
4. Light tightness is a closed box standing on the target, not a roof.
5. Component dimensions are confirmed before the holder is drawn.

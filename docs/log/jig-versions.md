# Test fixture, version history

How the fixture got to V6, and why each version was thrown away. The reasons
are the design rules for the sensor ring, which is why they are written down.

## V1, 2026-09-08

Base plate with a card pocket, a bridge over it carrying the sensor board, and
five printed aperture discs of 5 mm diameter with holes from 0.6 to 3.0 mm.
LED channels bored at 28 degrees through the solid bridge.

Discarded:

- The 0.6 mm printed hole did not exist after printing, even at 0.08 mm layer
  height. FDM does not make clean holes below about 1.5 mm.
- 5 mm discs are too small to handle and cannot be seated repeatably.
- Angled bores through a solid body print badly. The roof of the bore sags and
  the LED sits crooked.
- The tunnel under the bridge was open along both long sides, so ambient light
  reached the card from the side.

## V2 and V3, 2026-09-09

The same bridge with light skirts along both edges, first with a 0.3 mm gap
above the card, then touching it. Fixed the side leak and none of the rest.

## V4, 2026-09-09

First modular stack: frame, aperture slide, sensor carrier, clamshell plugs for
3 mm LEDs, rail. Every part flat, every bore vertical in print orientation, the
aperture moved out of the printer and into a pierced black card.

Discarded before printing: the LEDs on hand are 5 mm, and the clamshell plug
does not scale to a 5 mm body inside the frame.

Lesson: confirm the dimensions of a component before drawing its holder.

## V5, 2026-09-09

The 5 mm LEDs moved out of the frame into their own blocks standing beside it,
each with a straight bore aimed at the measurement spot and an outer face cut
perpendicular to that bore, so the part prints standing with the bore vertical.
Pins of 1.75 mm filament aligned the stack.

Discarded: the pins align but hold nothing. The stack rattled, and a rattling
stack changes the geometry between two series, which is the one thing a
reference fixture must not do.

## V6, 2026-09-10, current

```
base plate   120 x 120 x 4    card pocket, four pegs
rail         120 x 60 x 4     locates frame and LED holders on the card
frame        46 x 46 x 14     light chamber, windows in two walls
slide        46 x 46 x 2      holds the aperture card
carrier      46 x 46 x 26     sensor pocket, 8 mm shaft
lid          46 x 46 x 2      closes the sensor pocket, slot for the header
LED holder   26 x 46 x 22     two off, 5 mm LED at 20 degrees
LED cap      11 x 28 x 3      two off, presses the LED flange flat
insert       20.3 x 20.3 x 3.2  carries an ALS-PT19 in the sensor pocket
```

Everything is screwed with M3 straight into the printed plastic. The stack no
longer moves between series.

### Rules that came out of V1 to V5

1. Every printed bore is vertical in its print orientation.
2. No printed hole below 1.5 mm. Small apertures go into black card.
3. Anything that has to be handled is at least 20 mm across.
4. Light tightness is a closed box standing on the target, not a roof over it.
5. Alignment is not fixation. If it can rattle, it will, and it will do it
   between two series.
6. Component dimensions are confirmed before the holder is drawn.

### Things that cost an evening and are worth writing down

**The breadboard rail is split in the middle.** The MOSFET had no ground at
all, and every measurement that followed was wrong until a multimeter found it.

**A logic level MOSFET from an unknown batch may not be one.** With 3.3 V on
the gate it held 2.1 V across drain and source instead of under 0.1. The LED
lit, dimly, and the contrast measurement still worked because contrast is a
ratio. The absolute numbers from that session are not comparable with later
ones and are labelled accordingly.

**The tower was a mistake.** A carrier that hangs the sensor deeper into the
chamber sounds like it gets closer to the card. It got further away, and the
phototransistor sat on the converter floor until the short carrier went back in.

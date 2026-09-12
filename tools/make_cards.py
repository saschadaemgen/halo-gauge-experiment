#!/usr/bin/env python3
"""
Test card generator for the halo-gauge-experiment.

Draws its own dial. Nothing is traced from a manufacturer's artwork, so the
cards can be published with the rest of the project. Only the geometry that
matters for the measurement is copied: dial diameter, scale range, sweep angle,
needle length, needle width at the measuring radius, and the needle colour.

    python3 make_cards.py --scale 3 --from 16 --to 24 --step 0.5
    python3 make_cards.py --dial 25 --max 30 --sweep 270 --scale 1

Every page is one 100 x 100 mm card with crop marks, a caption naming the
position, and a 50 mm check ruler so a wrongly scaled print is obvious.

Needs reportlab:  pip3 install reportlab
"""

import argparse
import math
import os

from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

CARD = 100.0          # card edge in mm, matches the pocket of the jig base plate
GREY = Color(0.45, 0.45, 0.45)
INK = Color(0.1, 0.1, 0.1)


def ang(value, lo, hi, sweep, zero_at_left=True):
    """Needle angle in degrees, measured counterclockwise from east.

    A gauge sweeps clockwise from its minimum on the left to its maximum on the
    right. With a 180 degree sweep the minimum sits at 180 degrees (west) and
    the maximum at 0 degrees (east).
    """
    frac = 0.0 if hi == lo else (value - lo) / (hi - lo)
    start = 90.0 + sweep / 2.0
    return start - frac * sweep


def needle_width_at(r, r_tip, r_tail, w_hub, w_tip):
    """Width of the needle at radius r. Linear taper from hub to tip."""
    t = (r + r_tail) / (r_tip + r_tail)
    t = max(0.0, min(1.0, t))
    return w_hub + (w_tip - w_hub) * t


def draw_needle(c, cx, cy, r_tip, r_tail, w_hub, w_tip, colour, angle_deg):
    """A long slender needle: w_hub wide at the tail, w_tip at the point.

    The width at any radius follows from these two numbers. That is the honest
    way round: a real needle is what it is, and the sensor has to cope with the
    width it finds at its own radius.
    """
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    pts = [(r_tip, w_tip / 2), (r_tip, -w_tip / 2),
           (-r_tail, -w_hub / 2), (-r_tail, w_hub / 2)]
    c.setFillColor(colour)
    p = c.beginPath()
    for i, (u, v) in enumerate(pts):
        x = cx + (u * ca - v * sa)
        y = cy + (u * sa + v * ca)
        p.moveTo(x, y) if i == 0 else p.lineTo(x, y)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def draw_dial(c, cx, cy, d, lo, hi, sweep, major, minor_per_major, face, ink):
    r = d / 2.0
    c.setFillColor(face)
    c.circle(cx, cy, r, stroke=0, fill=1)
    c.setStrokeColor(ink)
    c.setLineWidth(r * 0.035)
    c.circle(cx, cy, r * 0.965, stroke=1, fill=0)

    n_major = int(round((hi - lo) / major))
    n_total = max(1, n_major * minor_per_major)
    for i in range(n_total + 1):
        value = lo + (hi - lo) * i / n_total
        a = math.radians(ang(value, lo, hi, sweep))
        is_major = (i % minor_per_major) == 0
        r_out = r * 0.90
        r_in = r * (0.79 if is_major else 0.855)
        c.setLineWidth(r * (0.038 if is_major else 0.018))
        c.setStrokeColor(ink)
        c.line(cx + math.cos(a) * r_in, cy + math.sin(a) * r_in,
               cx + math.cos(a) * r_out, cy + math.sin(a) * r_out)
        if is_major:
            c.setFont("Helvetica-Bold", r * 0.15)
            c.setFillColor(ink)
            rt = r * 0.66
            c.drawCentredString(cx + math.cos(a) * rt,
                                cy + math.sin(a) * rt - r * 0.053, "%g" % value)


def card_page(c, args, value, index, total):
    x0 = (210.0 - CARD) / 2.0 * mm          # centred on A4 portrait
    y0 = (297.0 - CARD) / 2.0 * mm
    face = HexColor(args.dial_colour)
    needle = HexColor(args.needle_colour)
    d = args.dial * args.scale
    # The sensor sits at a fixed point in the jig, args.sensor_offset above the
    # card centre. At any scale other than 1:1 the dial has to move so that this
    # point falls on the measuring radius, otherwise the sensor stares at the hub.
    shift = 0.0
    if args.centre == "sensor":
        shift = args.sensor_offset - args.radius * args.scale
    cx = x0 + CARD / 2 * mm
    cy = y0 + CARD / 2 * mm + shift * mm

    c.setFillColor(face)
    c.rect(x0, y0, CARD * mm, CARD * mm, stroke=0, fill=1)

    draw_dial(c, cx, cy, d * mm, args.lo, args.hi, args.sweep,
              args.major, args.minor, face, INK)

    r_meas = args.radius * args.scale
    r_tip = d * mm * 0.42
    r_tail = d * mm * 0.085
    draw_needle(c, cx, cy, r_tip=r_tip, r_tail=r_tail,
                w_hub=args.needle_hub * args.scale * mm,
                w_tip=args.needle_tip * args.scale * mm,
                colour=needle, angle_deg=ang(value, args.lo, args.hi, args.sweep))
    c.setFillColor(INK)
    c.circle(cx, cy, d * mm * 0.05, stroke=0, fill=1)

    # the radius the sensor looks at, as a faint reference ring
    if args.show_radius:
        c.setStrokeColor(Color(0.75, 0.75, 0.75))
        c.setLineWidth(0.15 * mm)
        c.setDash(1, 2)
        c.circle(cx, cy, r_meas * mm, stroke=1, fill=0)
        c.setDash()

    if args.show_radius:
        sx, sy = x0 + CARD / 2 * mm, y0 + CARD / 2 * mm + args.sensor_offset * mm
        c.setStrokeColor(Color(0.62, 0.62, 0.62))
        c.setLineWidth(0.2 * mm)
        c.setDash(1, 2)
        c.circle(sx, sy, 2.4 * mm, stroke=1, fill=0)
        c.setDash()
        c.line(sx - 4 * mm, sy, sx - 2.8 * mm, sy)
        c.line(sx + 2.8 * mm, sy, sx + 4 * mm, sy)

    # cut line and crop marks
    c.setStrokeColor(GREY)
    c.setLineWidth(0.15 * mm)
    c.rect(x0, y0, CARD * mm, CARD * mm, stroke=1, fill=0)
    c.setStrokeColor(black)
    c.setLineWidth(0.2 * mm)
    g, L = 1.5 * mm, 4 * mm
    for px, sx in ((x0, -1), (x0 + CARD * mm, 1)):
        for py, sy in ((y0, -1), (y0 + CARD * mm, 1)):
            c.line(px + sx * g, py, px + sx * (g + L), py)
            c.line(px, py + sy * g, px, py + sy * (g + L))

    # caption above, ruler below
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    label = "%s %s" % (fmt_value(value, args.step), args.unit)
    c.drawString(x0, y0 + CARD * mm + 7 * mm, "HGE-D%02d   %s" % (index, label))
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GREY)
    w_at = needle_width_at(args.radius * args.scale * mm, r_tip, r_tail,
                           args.needle_hub * args.scale * mm,
                           args.needle_tip * args.scale * mm) / mm
    c.drawString(x0, y0 + CARD * mm + 3 * mm,
                 "dial %g mm at %g:1, needle %.2f mm wide at r %g mm, sweep %g deg, "
                 "dial centre %+.1f mm, %d of %d"
                 % (args.dial, args.scale, w_at, args.radius * args.scale,
                    args.sweep, shift, index, total))
    c.setFont("Helvetica", 6.5)
    c.drawString(x0, y0 - 12 * mm,
                 "PRINT AT 100 %, NO SCALING. halo-gauge-experiment, Sascha Daemgen. "
                 "Original artwork, not a copy of any manufacturer's dial.")
    ry = y0 - 6 * mm
    c.setStrokeColor(black)
    c.setLineWidth(0.25 * mm)
    c.line(x0, ry, x0 + 50 * mm, ry)
    for i in range(51):
        t = 2.5 * mm if i % 10 == 0 else (1.6 * mm if i % 5 == 0 else 0.9 * mm)
        c.setLineWidth(0.25 * mm if i % 10 == 0 else 0.12 * mm)
        c.line(x0 + i * mm, ry, x0 + i * mm, ry - t)
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(INK)
    c.drawString(x0 + 52 * mm, ry - 2 * mm, "50 mm check")
    c.showPage()


def fmt_value(v, step):
    dec = 0 if abs(step - round(step)) < 1e-9 else (1 if abs(step * 10 - round(step * 10)) < 1e-9 else 2)
    return ("%%.%df" % dec) % v


def main():
    ap = argparse.ArgumentParser(description="test cards for the halo gauge experiment")
    ap.add_argument("--dial", type=float, default=20.0, help="dial diameter in mm at 1:1")
    ap.add_argument("--min", dest="lo", type=float, default=0.0)
    ap.add_argument("--max", dest="hi", type=float, default=40.0)
    ap.add_argument("--unit", default="MPa")
    ap.add_argument("--sweep", type=float, default=180.0, help="needle sweep in degrees")
    ap.add_argument("--major", type=float, default=10.0, help="numbered tick every")
    ap.add_argument("--minor", type=int, default=5, help="ticks per numbered tick")
    ap.add_argument("--radius", type=float, default=7.0,
                    help="measuring radius in mm at 1:1, where the sensor ring sits")
    ap.add_argument("--needle-hub", type=float, default=1.8,
                    help="needle width in mm at the hub, at 1:1")
    ap.add_argument("--needle-tip", type=float, default=0.35,
                    help="needle width in mm at the point, at 1:1")
    ap.add_argument("--needle-colour", default="#FCB803")
    ap.add_argument("--dial-colour", default="#FFFFFF")
    ap.add_argument("--scale", type=float, default=3.0, help="print magnification")
    ap.add_argument("--from", dest="start", type=float, default=None)
    ap.add_argument("--to", dest="stop", type=float, default=None)
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--sensor-offset", type=float, default=7.0,
                    help="fixed distance in mm from the card centre to the sensor in the jig")
    ap.add_argument("--centre", choices=["card", "sensor"], default="sensor",
                    help="card: dial in the middle of the card. sensor: shift the dial so the "
                         "jig's fixed sensor position lands on the measuring radius")
    ap.add_argument("--show-radius", action="store_true",
                    help="draw the measuring radius as a dashed ring")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    start = args.lo if args.start is None else args.start
    stop = args.hi if args.stop is None else args.stop
    values, v = [], start
    while v <= stop + 1e-9 and len(values) < 200:
        values.append(round(v, 6))
        v += args.step

    shift = (args.sensor_offset - args.radius * args.scale) if args.centre == "sensor" else 0.0
    reach = args.dial * args.scale / 2 + abs(shift)
    if reach > 49:
        raise SystemExit(
            "dial %g mm at %g:1 with a %+.1f mm shift reaches %.1f mm from the card centre, "
            "a 100 mm card only holds 49. use a smaller scale or --centre card."
            % (args.dial, args.scale, shift, reach))

    out = args.out or ("hge_cards_%gx_%s_to_%s.pdf" %
                       (args.scale, fmt_value(start, args.step), fmt_value(stop, args.step)))
    out = os.path.abspath(out)
    c = canvas.Canvas(out, pagesize=(210 * mm, 297 * mm))
    c.setTitle("halo-gauge-experiment test cards")
    c.setAuthor("Sascha Daemgen")
    for i, value in enumerate(values, 1):
        card_page(c, args, value, i, len(values))
    c.save()
    print("%d cards written to %s" % (len(values), out))
    r_tip = args.dial * args.scale * mm * 0.42
    r_tail = args.dial * args.scale * mm * 0.085
    w_at = needle_width_at(args.radius * args.scale * mm, r_tip, r_tail,
                           args.needle_hub * args.scale * mm,
                           args.needle_tip * args.scale * mm) / mm
    print("at the measuring radius r %g mm the needle is %.2f mm wide on the print,"
          % (args.radius * args.scale, w_at))
    print("which is %.2f mm at 1:1. a 1.6 mm sensor scales to %.1f mm,"
          % (w_at / args.scale, 1.6 * args.scale))
    print("so the aperture in the jig should be about %.1f mm for an honest test."
          % (1.6 * args.scale))
    if args.centre == "sensor":
        print("dial centre shifted %+.1f mm so the sensor at %g mm sits on the measuring radius."
              % (shift, args.sensor_offset))


if __name__ == "__main__":
    main()

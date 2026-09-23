# -*- coding: utf-8 -*-
"""Sweep the rise/fall angles and lead to pick defaults that match the sketch.

With five control points the loop cannot have a true flat top (only the apex
point can reach the clearance), so this script measures the two features the
reference sketch does show:

* ``top flat`` - how much of the crest stays within 2% of the clearance;
* ``descent straight`` - deviation of the descent from a straight line.

Run:  python scripts/scan_angles.py
"""

import math

import numpy as np

MAX_ANGLE = 89.0
HEIGHT = 0.15
LENGTH = 0.70


def loop_profile(length, peak_ratio=0.42, rise_angle=60.0, fall_angle=30.0,
                 lead_distance=0.01, clearance=HEIGHT):
    ratio = min(max(float(peak_ratio), 0.05), 0.95)
    peak_u = length * ratio
    rise = math.radians(min(max(rise_angle, 0.0), MAX_ANGLE))
    fall = math.radians(min(max(fall_angle, 0.0), MAX_ANGLE))
    du_b = min(lead_distance * math.cos(rise), peak_u * 0.98)
    du_d = min(lead_distance * math.cos(fall),
               max(length * (1.0 - ratio), 1e-9) * 0.98)
    return [(0.0, 0.0), (du_b, lead_distance * math.sin(rise)),
            (peak_u, clearance),
            (length - du_d, lead_distance * math.sin(fall)), (length, 0.0)]


def natural_spline(u, v, samples=800):
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)
    t = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(u), np.diff(v)))))
    t /= t[-1]
    n = len(t) - 1
    h = np.diff(t)

    def build(values):
        alpha = np.zeros(n + 1)
        for i in range(1, n):
            alpha[i] = (3.0 / h[i] * (values[i + 1] - values[i])
                        - 3.0 / h[i - 1] * (values[i] - values[i - 1]))
        l = np.zeros(n + 1)
        mu = np.zeros(n + 1)
        z = np.zeros(n + 1)
        l[0] = 1.0
        for i in range(1, n):
            l[i] = 2.0 * (t[i + 1] - t[i - 1]) - h[i - 1] * mu[i - 1]
            mu[i] = h[i] / l[i]
            z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i]
        l[n] = 1.0
        c = np.zeros(n + 1)
        b = np.zeros(n + 1)
        d = np.zeros(n + 1)
        for j in range(n - 1, -1, -1):
            c[j] = z[j] - mu[j] * c[j + 1]
            b[j] = ((values[j + 1] - values[j]) / h[j]
                    - h[j] * (c[j + 1] + 2.0 * c[j]) / 3.0)
            d[j] = (c[j + 1] - c[j]) / (3.0 * h[j])
        return b, c, d

    ts = np.linspace(0.0, 1.0, samples)
    bu, cu, du = build(u)
    bv, cv, dv = build(v)
    xs = np.empty_like(ts)
    ys = np.empty_like(ts)
    for k, value in enumerate(ts):
        j = max(0, min(n - 1, np.searchsorted(t, value, side="right") - 1))
        dt = value - t[j]
        xs[k] = u[j] + bu[j] * dt + cu[j] * dt ** 2 + du[j] * dt ** 3
        ys[k] = v[j] + bv[j] * dt + cv[j] * dt ** 2 + dv[j] * dt ** 3
    return xs, ys


def metrics(rise, fall, lead_mm):
    pts = loop_profile(LENGTH, rise_angle=rise, fall_angle=fall,
                       lead_distance=lead_mm)
    us = np.array([p[0] for p in pts])
    vs = np.array([p[1] for p in pts])
    xs, ys = natural_spline(us, vs)

    top = ys >= HEIGHT * 0.98
    flat = (xs[top].max() - xs[top].min()) * 1000 if top.any() else 0.0

    u0, v0 = us[2], vs[2]
    u1, v1 = us[3], vs[3]
    inside = (xs > u0) & (xs < u1)
    if inside.sum() > 5:
        straight = v0 + (v1 - v0) * (xs[inside] - u0) / (u1 - u0)
        bulge = np.max(np.abs(ys[inside] - straight)) / abs(v0 - v1) * 100.0
    else:
        bulge = float("nan")
    return ys.max() / HEIGHT - 1.0, flat, bulge


print("=== effect of the rise angle (lead 60 um, fall 30 deg) ===")
print(" rise | height err | top flat | descent bulge")
for rise in (45, 60, 70, 75, 80, 85):
    err, flat, bulge = metrics(rise, 30, 0.060)
    print("  %3d  |   %+5.1f%%   | %6.1f um |    %5.1f%%" % (rise, err * 100, flat, bulge))

print("\n=== effect of the lead length (rise 60, fall 30) ===")
print(" lead | height err | top flat | descent bulge")
for lead in (10, 30, 60, 100, 150):
    err, flat, bulge = metrics(60, 30, lead / 1000.0)
    print("  %4d |   %+5.1f%%   | %6.1f um |    %5.1f%%" % (lead, err * 100, flat, bulge))

print("\n=== both angles high with a long lead ===")
print(" rise/fall | lead | height err | top flat | descent bulge")
for rise, fall in ((80, 80), (85, 85), (75, 60), (80, 50)):
    for lead in (60, 100, 150):
        err, flat, bulge = metrics(rise, fall, lead / 1000.0)
        print("   %3d/%-3d  | %4d |   %+5.1f%%   | %6.1f um |    %5.1f%%"
              % (rise, fall, lead, err * 100, flat, bulge))

print("\nreference sketch: top flat ~120-210 um, descent essentially straight")

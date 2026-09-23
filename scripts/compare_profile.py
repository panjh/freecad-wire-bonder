# -*- coding: utf-8 -*-
"""Compare the generated wire loop against the reference bonder sketch.

The loop now has five control points A -> B -> C -> D -> E (see
``docs/spline-ctrl-points.md``):

* A - start, on the first pad;
* B - ``AB = lead_distance`` along the rise ray leaving A;
* C - apex, placed by ``peak_ratio`` and ``clearance``;
* D - ``ED = lead_distance`` along the fall ray leaving E;
* E - end, on the second pad.

Both angles are measured from the A-E line: 0 deg points at the other pad,
90 deg is perpendicular to it.

The reference sketch (``data/wire-sketch.png``) uses
``L' = 700 um``, ``H' = 150 um``, a lead of about ``60 um`` and a steep take-off.

This script prints the control points plus the derived spans and angles, and
writes a comparison plot to ``docs/images/loop-shape.png``.

Run:  python scripts/compare_profile.py
"""

import math
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager

# ``core.loop_profile()`` cannot be imported here because core.py needs FreeCAD.
# The formulas below are a verbatim copy; keep the two in step.
MAX_LEAD_FRACTION = 0.30
MAX_ANGLE = 89.0
DEFAULT_PEAK_RATIO = 0.42
DEFAULT_CLEARANCE = 0.5
DEFAULT_RISE_ANGLE = 75.0
DEFAULT_FALL_ANGLE = 20.0
DEFAULT_LEAD_DISTANCE = 0.03

_available = {f.name for f in font_manager.fontManager.ttflist}
for _candidate in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun"):
    if _candidate in _available:
        plt.rcParams["font.sans-serif"] = [_candidate]
        break
plt.rcParams["axes.unicode_minus"] = False


def loop_profile(length, clearance, peak_ratio=DEFAULT_PEAK_RATIO,
                 rise_angle=DEFAULT_RISE_ANGLE, fall_angle=DEFAULT_FALL_ANGLE,
                 lead_distance=DEFAULT_LEAD_DISTANCE):
    """Copy of ``WireBonder.core.loop_profile()`` (see that docstring)."""
    length = float(length)
    height = float(clearance)
    ratio = min(max(float(peak_ratio), 0.05), 0.95)
    peak_u = length * ratio

    lead = float(lead_distance or 0.0) or DEFAULT_LEAD_DISTANCE
    rise = math.radians(min(max(float(rise_angle), 0.0), MAX_ANGLE))
    fall = math.radians(min(max(float(fall_angle), 0.0), MAX_ANGLE))

    du_b = lead * math.cos(rise)
    du_d = lead * math.cos(fall)
    room = max(length * (1.0 - ratio), 1e-9)
    if du_b > 0.0 and peak_u > 0.0:
        du_b = min(du_b, peak_u * 0.98)
    if du_d > 0.0 and room > 0.0:
        du_d = min(du_d, room * 0.98)

    return [
        (0.0, 0.0),                                              # A
        (du_b, lead * math.sin(rise)),                           # B
        (peak_u, height),                                        # C
        (length - du_d, lead * math.sin(fall)),                  # D
        (length, 0.0),                                           # E
    ]


def natural_spline(u, v, samples=600):
    """Chord-length parameterised cubic spline (same approach as FreeCAD)."""
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


# ----------------------------------------------------------------------
# reference dimensions from the sketch
# ----------------------------------------------------------------------
REF_L = 0.700     # mm, pad centre distance
REF_H = 0.150     # mm, loop height
REF_RISE = 75.0   # deg
REF_FALL = 20.0   # deg
REF_LEAD = 0.03   # mm, 30 um along each ray


def report(tag, points, length):
    us = np.array([p[0] for p in points])
    vs = np.array([p[1] for p in points])
    xs, ys = natural_spline(us, vs)
    c = 2                                     # apex index
    d = 3                                     # fall point index
    rise_deg = math.degrees(math.atan2(vs[1], us[1])) if us[1] else 90.0
    fall_deg = math.degrees(math.atan2(vs[d], length - us[d])) if length > us[d] else 90.0
    m = (xs > us[c]) & (xs < us[d] + 1e-12)
    slope = float("nan")
    if m.sum() > 5:
        slope = np.polyfit(xs[m], ys[m], 1)[0]
    print("   %-16s peak %.4f mm | rise %4.1f deg | fall %4.1f deg | "
          "descent slope %+.3f"
          % (tag, vs.max(), rise_deg, fall_deg, slope))


print("=== reference expectations (L'=700um, H'=150um, lead 60um) ===")
print("   a steep take-off, an apex around 0.42 L', then a long descent")

print("\n=== generated profile ===")
ref = loop_profile(REF_L, REF_H, rise_angle=REF_RISE, fall_angle=REF_FALL,
                   lead_distance=REF_LEAD)
report("defaults", loop_profile(REF_L, REF_H), REF_L)
report("steep rise 85", loop_profile(REF_L, REF_H, rise_angle=85.0), REF_L)
report("shallow fall 10", loop_profile(REF_L, REF_H, fall_angle=10.0), REF_L)
report("symmetric 45/45", loop_profile(REF_L, REF_H, rise_angle=45.0,
                                       fall_angle=45.0), REF_L)

print("\n=== control points of the reference fit (um) ===")
for name, (u, v) in zip("ABCDE", ref):
    print("   %s: u = %7.1f   v = %6.1f" % (name, u * 1000, v * 1000))
print("   AB = %.1f um, ED = %.1f um"
      % (math.hypot(ref[1][0], ref[1][1]) * 1000,
         math.hypot(REF_L - ref[3][0], ref[3][1]) * 1000))

# ----------------------------------------------------------------------
# plot
# ----------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 6.4), dpi=150)

xs, ys = natural_spline([p[0] for p in ref], [p[1] for p in ref])
ax.plot(xs * 1000, ys * 1000, color="#C0392B", linewidth=2.8,
        label="生成的弧线（5 个控制点 A–E）")
ax.plot([p[0] * 1000 for p in ref], [p[1] * 1000 for p in ref],
        "o", color="#2C3E50", markersize=6, label="控制点 A B C D E")

for name, (u, v) in zip("ABCDE", ref):
    ax.annotate(name, xy=(u * 1000, v * 1000),
                xytext=(u * 1000 + 8, v * 1000 + 12),
                fontsize=11, color="#2C3E50", fontweight="bold")

# the two rays that define B and D
ax.plot([0, ref[1][0] * 1000], [0, ref[1][1] * 1000], ":",
        color="#2E7D32", linewidth=1.4)
ax.plot([REF_L * 1000, ref[3][0] * 1000], [0, ref[3][1] * 1000], ":",
        color="#2E7D32", linewidth=1.4)

ax.axhline(REF_H * 1000, color="#95A5A6", linewidth=0.8, linestyle=":")
ax.text(10, REF_H * 1000 + 4, "H' = 150 µm 弧高", fontsize=9, color="#7F8C8D")
ax.annotate("AB = 进球距离 %.0f µm\n%.0f° 出线角" % (REF_LEAD * 1000, REF_RISE),
            xy=(ref[1][0] * 1000, ref[1][1] * 1000),
            xytext=(60, 62), fontsize=9, color="#2E7D32",
            arrowprops=dict(arrowstyle="->", color="#2E7D32"))
ax.annotate("ED = 落球距离 %.0f µm\n%.0f° 落线角" % (REF_LEAD * 1000, REF_FALL),
            xy=(ref[3][0] * 1000, ref[3][1] * 1000),
            xytext=(430, 62), fontsize=9, color="#2E7D32",
            arrowprops=dict(arrowstyle="->", color="#2E7D32"))
ax.annotate("C 顶点 (peak_ratio, clearance)",
            xy=(ref[2][0] * 1000, ref[2][1] * 1000),
            xytext=(150, REF_H * 1000 + 30), fontsize=9.5, color="#C0392B",
            arrowprops=dict(arrowstyle="->", color="#C0392B"))

ax.set_title("打线弧 5 控制点线形（L′=700 µm，H′=150 µm）", fontsize=12.5)
ax.set_xlabel("u（沿焊盘中心连线，µm）")
ax.set_ylabel("v（相对连线的弧高，µm）")
ax.set_xlim(-25, REF_L * 1000 + 25)
ax.set_ylim(-12, REF_H * 1000 + 55)
ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
ax.legend(loc="upper right", fontsize=9)
fig.tight_layout()

out_dir = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "docs", "images")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "loop-shape.png")
fig.savefig(out_path)
plt.close(fig)
print("\nsaved:", out_path)

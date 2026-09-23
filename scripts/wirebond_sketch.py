# -*- coding: utf-8 -*-
"""Draw a diagram of one real WireBond object from its measured parameters.

Reads ``data/wirebond_params.json`` (written by the FreeCAD-side export) and
produces a two-panel figure:

* **left**  - the loop in the wire plane, in the local ``(u, v)`` coordinates the
  addon works in: the B-spline, the five control points A-E, the two
  entry/exit rays and the parameter annotations;
* **right** - the same curve in 3D, with the two pad centroids and their
  normals, so the spatial arrangement is visible.

The JSON holds the object's parameters, its coordinate frame and a sampling of
its centreline. The curve is **rebuilt here from the loop parameters** rather
than taken from the swept solid, because that solid does not contain the
centreline: its edges are offset by the wire radius (about 6 µm at 20 µm
diameter), which would make the peak look 2-3% too low.

The five loop parameters sit at the very top of the CONFIG block. ``None``
means "use the value exported from the object"; set a number to override it and
the figure is drawn from that value instead (the caption then says so).

Run:  python scripts/wirebond_sketch.py

Everything that can reasonably be changed lives in the CONFIG block; the rest
of the file only draws.
"""

import json
import math
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers the 3d projection)

# ======================================================================
# CONFIG - user settings, edit here
# ======================================================================

# ---- wire loop parameters -------------------------------------------------
# These five drive the shape. Values are taken from the exported object unless
# the matching LOOP_PROFILE entry below is set to a number.
#
#   um      micrometres (clearance and lead distance)
#   deg     degrees from the pad-to-pad line; 0 = along it, 90 = perpendicular
#   ratio   0..1 of the span; where the apex sits between the two pads
LOOP_PROFILE = {
    "CLEARANCE": 200,        # um  - apex height above the pad-to-pad line
    "LEAD_DISTANCE": 100,    # um  - distance from each pad along its ray to B/D
    "RISE_ANGLE": 90,       # deg - direction the wire leaves the first pad
    "FALL_ANGLE": 10,       # deg - direction it reaches the second pad
    "PEAK_RATIO": 0.1,       # -   - apex position as a fraction of the span
}

# Give the text computed from the parameters, and mark any value that was
# overridden so the figure does not silently disagree with the object.
LOOP_PROFILE_LABEL = "中心线（按对象参数重建）"
LOOP_PROFILE_LABEL_EDITED = "中心线（按本脚本的参数绘制）"

# ---- input / output (paths are relative to the repository root) ----
INPUT_JSON = os.path.join("data", "wirebond_params.json")
OUTPUT_PNG = os.path.join("data", "wirebond_sketch.png")

# ---- figure ----
FIG_SIZE = (15.5, 7.2)          # inches
FIG_DPI = 150
FONT_CANDIDATES = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun")
TITLE_LEFT = "走线平面内的剖面（局部坐标 u–v）"
TITLE_RIGHT = "三维布置（全局坐标，单位 mm）"
LABEL_X = "u（沿两焊盘质心连线，µm）"
LABEL_Y = "v（相对该连线的高度，µm）"
LABEL_3D = ("X (mm)", "Y (mm)", "Z (mm)")

# ---- geometry units ----
UM_PER_MM = 1000.0              # the JSON is in millimetres, the plot in µm
CONTROL_POINT_NAMES = "ABCDE"   # five control points, A = start, E = end

# ---- colours ----
COLOUR_CURVE = "#C0392B"        # the wire centreline
COLOUR_POINTS = "#2C3E50"       # control points and their labels
COLOUR_RAY = "#2E7D32"          # entry / exit ray and the angle annotations
COLOUR_GUIDE = "#7F8C8D"        # clearance marker and axis hints
COLOUR_FACE = ("#1F77B4", "#FF7F0E")   # start / end pad

# ---- line weights ----
LW_CURVE_2D = 3.0
LW_CURVE_3D = 2.6
LW_RAY = 1.6
LW_GUIDE = 0.9
LW_TUBE = 6.5                   # faint "wire body" drawn around the centreline
TUBE_ALPHA = 0.22
MARKER_SIZE = 7

# ---- annotation layout (offsets in µm / axis fractions) ----
ANN_LABEL_OFFSET = (7, 14)      # A..E letter offset from its point
ANN_RISE_OFFSET = (55, 52)      # rise-angle callout, from B
ANN_FALL_OFFSET = (-150, 62)    # fall-angle callout, from D
ANN_PEAK_OFFSET = (-40, 42)     # apex callout, from C
CLEARANCE_LABEL_X = 12          # shift of the clearance text from the vertex
CLEARANCE_LABEL_Y = 0.52        # fraction of the clearance
RISE_RAY_LENGTH = 46            # length of the u-axis hint arrow

# ---- limits and 3D view ----
# x runs from XLIM_MIN to L + XLIM_MAX_PAD, y from YLIM_MIN to
# clearance * YLIM_TOP_FACTOR (all in µm)
XLIM_MIN = -30
XLIM_MAX_PAD = 40
YLIM_MIN = -46
YLIM_TOP_FACTOR = 1.30
VIEW_ELEV, VIEW_AZIM = 22, -58  # 3D camera
AXES_RECT_LEFT = (0.055, 0.10, 0.52, 0.80)
AXES_RECT_RIGHT = (0.63, 0.06, 0.35, 0.86)
CAPTION_Y = 0.015

# ---- text ----
LABEL_CURVE = "中心线（按对象参数重建）"
LABEL_POINTS = "5 个控制点 A–E"
LABEL_START, LABEL_END = "起点 A", "终点 E"
TEXT_U_AXIS = "u（沿焊盘中心连线）"
TEXT_CLEARANCE = "Clearance\n%.0f µm"
TEXT_RISE = "出线角 %.1f°\nAB = %.0f µm"
TEXT_FALL = "落线角 %.1f°\nED = %.0f µm"
TEXT_PEAK = "顶点 C\npeak_ratio %.2f × L"
TEXT_SOLID_ON, TEXT_SOLID_OFF = "含金线实体", "仅中心线"
CAPTION = ("对象 %s ｜ 中心线弧长 %.3f mm ｜ 线径 %.0f µm ｜ 跨度 L = %.0f µm ｜ "
           "净空 %.0f µm ｜ 出线/落线 %.1f°/%.1f° ｜ 进出线 %.0f µm ｜ %s")

# ---- printed report ----
REPORT_KEYS = ("Clearance", "PeakRatio", "RiseAngle", "FallAngle",
               "LeadDistance", "WireDiameter", "BallDiameter")

# ======================================================================
# end of CONFIG - drawing code below
# ======================================================================

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, INPUT_JSON)
OUT = os.path.join(ROOT, OUTPUT_PNG)

# ---- loop geometry -----------------------------------------------------
# Copy of WireBonder.core.loop_profile(): the addon cannot be imported here
# because core.py needs FreeCAD. Keep the two in step if the rules change.
MAX_ANGLE = 89.0


def loop_profile(length, clearance, peak_ratio, rise_angle, fall_angle,
                 lead_distance):
    """Return the five control points A-E in local ``(u, v)`` millimetres.

    ``lead`` and the angles position B and D on the rays leaving A and E; the
    horizontal part of a lead is clamped so B stays before C and D after it,
    which the spline interpolation requires (strictly increasing ``u``).
    """
    length = float(length)
    clearance = float(clearance)
    ratio = min(max(float(peak_ratio), 0.05), 0.95)
    peak_u = length * ratio

    lead = float(lead_distance) or 1e-6
    rise = math.radians(min(max(float(rise_angle), 0.0), MAX_ANGLE))
    fall = math.radians(min(max(float(fall_angle), 0.0), MAX_ANGLE))

    du_b = lead * math.cos(rise)
    du_d = lead * math.cos(fall)
    if du_b > 0.0 and peak_u > 0.0:
        du_b = min(du_b, peak_u * 0.98)
    if du_d > 0.0:
        du_d = min(du_d, max(length * (1.0 - ratio), 1e-9) * 0.98)

    return [
        (0.0, 0.0),                                                  # A
        (du_b, lead * math.sin(rise)),                               # B
        (peak_u, clearance),                                         # C
        (length - du_d, lead * math.sin(fall)),                      # D
        (length, 0.0),                                               # E
    ]


def sample_curve(points2d, samples=600):
    """Sample the interpolating B-spline built from ``points2d``.

    Uses a chord-length parameterised natural cubic spline, the same model as
    ``Part.BSplineCurve.interpolate()``, so the figure shows the curve FreeCAD
    would build from these control points.
    """
    u = np.asarray([p[0] for p in points2d], dtype=float)
    v = np.asarray([p[1] for p in points2d], dtype=float)
    t = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(u), np.diff(v)))))
    t = t / t[-1]
    n = len(t) - 1
    h = np.diff(t)

    def coefficients(values):
        alpha = np.zeros(n + 1)
        for i in range(1, n):
            alpha[i] = (3.0 / h[i] * (values[i + 1] - values[i])
                        - 3.0 / h[i - 1] * (values[i] - values[i - 1]))
        lower = np.zeros(n + 1)
        mu = np.zeros(n + 1)
        z = np.zeros(n + 1)
        lower[0] = 1.0
        for i in range(1, n):
            lower[i] = (2.0 * (t[i + 1] - t[i - 1]) - h[i - 1] * mu[i - 1])
            mu[i] = h[i] / lower[i]
            z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / lower[i]
        lower[n] = 1.0
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
    bu, cu, du = coefficients(u)
    bv, cv, dv = coefficients(v)
    xs = np.empty_like(ts)
    ys = np.empty_like(ts)
    for k, value in enumerate(ts):
        j = max(0, min(n - 1, int(np.searchsorted(t, value, side="right")) - 1))
        dt = value - t[j]
        xs[k] = u[j] + bu[j] * dt + cu[j] * dt ** 2 + du[j] * dt ** 3
        ys[k] = v[j] + bv[j] * dt + cv[j] * dt ** 2 + dv[j] * dt ** 3
    return xs, ys


def map_to_world(points2d, frame_data):
    """Map local ``(u, v)`` onto the global axis of the exported frame."""
    origin = np.array(frame_data["origin"], dtype=float)
    xdir = np.array(frame_data["xdir"], dtype=float)
    ydir = np.array(frame_data["ydir"], dtype=float)
    return origin + np.outer(points2d[:, 0], xdir) + np.outer(points2d[:, 1], ydir)

_available = {f.name for f in font_manager.fontManager.ttflist}
for _candidate in FONT_CANDIDATES:
    if _candidate in _available:
        plt.rcParams["font.sans-serif"] = [_candidate]
        break
plt.rcParams["axes.unicode_minus"] = False
UM = UM_PER_MM

with open(SRC, encoding="utf-8") as fh:
    data = json.load(fh)

params = data["parameters"]
faces = data["faces"]
names = CONTROL_POINT_NAMES

L = data["frame"]["length"]
diameter = params["WireDiameter"]

# The exported values, then any override from LOOP_PROFILE on top of them.
_fallback = {
    "CLEARANCE": params["Clearance"] * UM,
    "LEAD_DISTANCE": params["LeadDistance"] * UM,
    "RISE_ANGLE": params["RiseAngle"],
    "FALL_ANGLE": params["FallAngle"],
    "PEAK_RATIO": params["PeakRatio"],
}
overridden = sorted(key for key, value in LOOP_PROFILE.items()
                    if value is not None)
values = {key: (LOOP_PROFILE[key] if LOOP_PROFILE[key] is not None
                else value)
          for key, value in _fallback.items()}

H = values["CLEARANCE"] / UM
lead = values["LEAD_DISTANCE"] / UM
rise = values["RISE_ANGLE"]
fall = values["FALL_ANGLE"]
peak_ratio = values["PEAK_RATIO"]

profile = loop_profile(L, H, peak_ratio, rise, fall, lead)
_uv = sample_curve(profile)
uv = np.column_stack(_uv)
xyz = map_to_world(uv, data["frame"])

if overridden:
    print("LOOP_PROFILE overrides active:", ", ".join(overridden))
    for key in overridden:
        print("   %-14s %s  (exported %s)"
              % (key, values[key], _fallback[key]))

fig = plt.figure(figsize=FIG_SIZE, dpi=FIG_DPI)
ax = fig.add_axes(AXES_RECT_LEFT)
ax3 = fig.add_axes(AXES_RECT_RIGHT, projection="3d")

# ---------------------------------------------------------------- left panel
curve_label = LOOP_PROFILE_LABEL_EDITED if overridden else LOOP_PROFILE_LABEL
ax.plot(uv[:, 0] * UM, uv[:, 1] * UM, color=COLOUR_CURVE, linewidth=LW_CURVE_2D,
        solid_capstyle="round", zorder=3, label=curve_label)

cx = [p[0] * UM for p in profile]
cy = [p[1] * UM for p in profile]
ax.plot(cx, cy, "o", color=COLOUR_POINTS, markersize=MARKER_SIZE, zorder=4,
        label=LABEL_POINTS)
ax.plot(cx, cy, color=COLOUR_POINTS, linewidth=1.0, linestyle=(0, (1, 2)),
        zorder=4)

for name, x, y in zip(names, cx, cy):
    ax.annotate(name, xy=(x, y),
                xytext=(x + ANN_LABEL_OFFSET[0], y + ANN_LABEL_OFFSET[1]),
                fontsize=12, fontweight="bold", color=COLOUR_POINTS)

# the two rays that define B and D
ax.plot([0, cx[1]], [0, cy[1]], ":", color=COLOUR_RAY, linewidth=LW_RAY)
ax.plot([cx[4], cx[3]], [cy[4], cy[3]], ":", color=COLOUR_RAY,
        linewidth=LW_RAY)

# u axis hint, along the pad-to-pad line
ax.annotate("", xy=(RISE_RAY_LENGTH, 0), xytext=(0, 0),
            arrowprops=dict(arrowstyle="->", color=COLOUR_GUIDE, lw=1.0))
ax.text(RISE_RAY_LENGTH * 0.65, YLIM_MIN * 0.74, TEXT_U_AXIS,
        fontsize=9, color=COLOUR_GUIDE)

# clearance guide
ax.axhline(H * UM, color="#95A5A6", linewidth=LW_GUIDE, linestyle=":")
ax.annotate("", xy=(cx[2], H * UM), xytext=(cx[2], 0),
            arrowprops=dict(arrowstyle="<->", color=COLOUR_GUIDE, lw=1.1))
ax.text(cx[2] + CLEARANCE_LABEL_X, H * UM * CLEARANCE_LABEL_Y,
        TEXT_CLEARANCE % (H * UM), fontsize=10, color=COLOUR_GUIDE)

ax.annotate(TEXT_RISE % (rise, lead * UM),
            xy=(cx[1], cy[1]),
            xytext=(cx[1] + ANN_RISE_OFFSET[0], cy[1] + ANN_RISE_OFFSET[1]),
            fontsize=10, color=COLOUR_RAY, ha="left",
            arrowprops=dict(arrowstyle="->", color=COLOUR_RAY))
ax.annotate(TEXT_FALL % (fall, lead * UM),
            xy=(cx[3], cy[3]),
            xytext=(cx[3] + ANN_FALL_OFFSET[0], cy[3] + ANN_FALL_OFFSET[1]),
            fontsize=10, color=COLOUR_RAY, ha="left",
            arrowprops=dict(arrowstyle="->", color=COLOUR_RAY))
ax.annotate(TEXT_PEAK % peak_ratio,
            xy=(cx[2], cy[2]),
            xytext=(cx[2] + ANN_PEAK_OFFSET[0], cy[2] + ANN_PEAK_OFFSET[1]),
            fontsize=10, color=COLOUR_CURVE, ha="center",
            arrowprops=dict(arrowstyle="->", color=COLOUR_CURVE))

ax.set_title(TITLE_LEFT, fontsize=12.5)
ax.set_xlabel(LABEL_X)
ax.set_ylabel(LABEL_Y)
ax.set_xlim(XLIM_MIN, L * UM + XLIM_MAX_PAD)
ax.set_ylim(YLIM_MIN, H * UM * YLIM_TOP_FACTOR)
ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
ax.legend(loc="upper right", fontsize=9.5)
ax.set_aspect("equal", adjustable="box")

# --------------------------------------------------------------- right panel
ax3.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], color=COLOUR_CURVE, linewidth=LW_TUBE,
         alpha=TUBE_ALPHA, zorder=4)
ax3.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], color=COLOUR_CURVE,
         linewidth=LW_CURVE_3D, zorder=5)

for index, face in enumerate(faces[:2]):
    centre = face["centre"]
    normal = np.array(face["normal"])
    colour = COLOUR_FACE[index]
    label = LABEL_START if index == 0 else LABEL_END
    ax3.scatter(*centre, color=colour, s=70, depthshade=False, zorder=6,
                label="%s (%s)" % (label, face["sub"]))
    ax3.quiver(*centre, *(normal * 0.09), color=colour, linewidth=1.6,
               arrow_length_ratio=0.35)

ax3.set_title(TITLE_RIGHT, fontsize=12.5)
ax3.set_xlabel(LABEL_3D[0], fontsize=9)
ax3.set_ylabel(LABEL_3D[1], fontsize=9)
ax3.set_zlabel(LABEL_3D[2], fontsize=9)
ax3.tick_params(labelsize=8)
ax3.legend(loc="upper left", fontsize=9)
ax3.view_init(elev=VIEW_ELEV, azim=VIEW_AZIM)

# ------------------------------------------------------------------- caption
solid_note = TEXT_SOLID_ON if params.get("MakeSolid") else TEXT_SOLID_OFF
centreline_length = data["shape"].get("centreline_length",
                                      data["shape"]["length"])
fig.text(0.5, CAPTION_Y,
         CAPTION % (data["label"], centreline_length, diameter * UM, L * UM,
                    H * UM, rise, fall, lead * UM, solid_note),
         ha="center", fontsize=10.5, color="#333333")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT)
plt.close(fig)
print("saved:", OUT)

# --------------------------------------------------------------- text report
print("\n=== geometry parameters in use ===")
for key in REPORT_KEYS:
    print("   %-14s %s" % (key, params[key]))
print("   span L        %.6f mm" % L)
print("   shape length  %.4f mm | volume %.6f mm3"
      % (data["shape"]["length"], data["shape"]["volume"]))
print("   loop in use   : clearance %.0f um, lead %.0f um, "
      "rise %.1f deg, fall %.1f deg, peak_ratio %.2f"
      % (H * UM, lead * UM, rise, fall, peak_ratio))

print("\n=== control points (um) ===")
for name, (u, v) in zip(names, profile):
    print("   %s (%8.2f, %7.2f)" % (name, u * UM, v * UM))

peak = float(np.max(uv[:, 1]))
print("\n   real curve peak: %.1f um (clearance %.1f um, %+.1f%%)"
      % (peak * UM, H * UM, (peak / H - 1.0) * 100))
print("   measured angle AB: %.1f deg"
      % math.degrees(math.atan2(profile[1][1], profile[1][0])))
print("   measured angle ED: %.1f deg"
      % math.degrees(math.atan2(profile[3][1], L - profile[3][0])))

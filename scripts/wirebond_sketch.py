#!env python
# -*- coding: utf-8 -*-
"""Draw the wire bond loop from parameters typed into this file.

This script is **self contained**: it reads no configuration file and needs no
FreeCAD. Set the parameters in the CONFIG block below, run it, and it writes a
figure of the loop in the wire plane (a side view) showing the B-spline, every
control point, the entry/exit rays and the key annotations.

Everything is expressed in **absolute view coordinates**, with A at the origin:

* **X** - horizontal, measured from A towards E (µm, positive to the right);
* **Y** - vertical, measured from A's own level (µm, positive upwards);
* **A** - fixed at ``(0, 0)``;
* **E** - at ``(SPAN, HEIGHT)``, so ``SPAN`` is the **horizontal (X) distance**
  from A to E and ``HEIGHT`` is how much higher E is than A (negative = E lower);
* **B**, **D** - ``LEAD_DISTANCE`` away from A / E along a ray whose angle is
  measured **from the horizontal plane** (``RISE_ANGLE`` at the start, ``FALL_ANGLE``
  at the landing: 0 deg = level, 90 deg = straight up). This is how a bonder is
  programmed, and it does not change when the two pads are not at the same height;
* **the loop points** - the ``(ratio, y)`` pairs in ``LOOP_POINTS``: ``ratio`` is
  the position **along the A-E span** (0 = A, 1 = E, so x = ratio * SPAN) and
  ``y`` is the **absolute** height in µm. Any number of them: one pair reproduces
  the classic single-apex loop, more pairs shape a flat top or a straight descent.

So the whole loop is built straight in X/Y - no local frame, no rotation.

Command line
------------
Both the console report and the figure annotations are bilingual (Chinese /
English) and selected with ``--lang``:

::

    python scripts/wirebond_sketch.py                 # Chinese (default)
    python scripts/wirebond_sketch.py --lang en       # English
    python scripts/wirebond_sketch.py --lang both     # both reports + two figures
    python scripts/wirebond_sketch.py -o out.png      # custom output path

``--lang both`` prints the Chinese report first and the English one after it, and
writes two figures (``..._zh.png`` and ``..._en.png``) derived from the output
path, so neither language has to share one crowded drawing.

The *console* report deliberately uses ASCII-safe units (``um``, ``deg``) so it
stays readable in a GBK Windows console; the *figure* uses the proper ``µm`` and
``°`` glyphs.
"""

import argparse
import math
import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager

# ======================================================================
# CONFIG - edit here, all lengths in micrometres, all coordinates absolute
#          (A is at the origin: X to the right, Y upwards)
# ======================================================================

# ---- loop parameters ------------------------------------------------------
SPAN = 264.0                    # um  - horizontal (X) distance from A to E
HEIGHT = -130.0                 # um  - E height relative to A: < 0 E is lower, > 0 higher
LOOP_POINTS = [(0.2, 200.0), (0.5, 200.0)]  # [(ratio, y), ...] the middle control points
#  ratio = position along the A-E span (0 = A, 1 = E)  ->  x = ratio * SPAN
#  y     = absolute height in um (A's level = 0)
#  one point = the classic apex; more points shape a flat top or a straight
#  descent, e.g. a flat top:   [(0.3, 200.0), (0.45, 200.0), (0.6, 200.0)]
LEAD_DISTANCE = 30.0            # um  - distance from each pad along its ray to B / D
RISE_ANGLE = 90.0               # deg - AB direction, from the HORIZONTAL plane
FALL_ANGLE = 15.0               # deg - ED direction, from the HORIZONTAL plane
WIRE_DIAMETER = 20.0            # um  - only used in the caption

# ---- figure ---------------------------------------------------------------
FIG_SIZE = (11.0, 6.4)          # inches
FIG_DPI = 150
#: Fonts able to render the Chinese annotations, in order of preference. The
#: English figure uses matplotlib's bundled DejaVu Sans instead, so it never
#: depends on a CJK font being installed.
FONT_CANDIDATES = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun")
FALLBACK_FONT = "DejaVu Sans"

# ---- style ----------------------------------------------------------------
COLOUR_CURVE = "#C0392B"        # the wire centreline
COLOUR_POINTS = "#2C3E50"       # control points and their labels
COLOUR_RAY = "#2E7D32"          # entry / exit ray and the angle annotations
COLOUR_GUIDE = "#7F8C8D"        # A-E line, level reference, peak guide
LW_CURVE = 3.0
LW_RAY = 1.6
LW_GUIDE = 0.9
MARKER_SIZE = 7

# ---- annotation layout (offsets in µm) ------------------------------------
ANN_LABEL_OFFSET = (7, 14)      # control point letter offset from its point
ANN_RISE_OFFSET = (40, 52)      # rise-angle callout, from B
ANN_FALL_OFFSET = (-170, 62)    # fall-angle callout, from D
ANN_PEAK_OFFSET = (-46, 42)     # loop point callout, from the highest point
PEAK_LABEL_X = 12               # shift of the peak text from its arrow
PEAK_LABEL_Y = 0.55             # position along the peak arrow (0 = level, 1 = peak)
LEVEL_REF_LENGTH = 70           # length of the level reference line at A, µm
XLIM_MARGIN_LEFT = 30           # margin left of the drawing, µm
XLIM_MARGIN_RIGHT = 40          # margin right of the drawing, µm
YLIM_MARGIN_BOTTOM = 45         # margin below the drawing, µm
YLIM_MARGIN_TOP = 60            # margin above the drawing, µm

# ======================================================================
# text - one block per language, selected with --lang
# ======================================================================
# Figure strings use the proper µm / ° glyphs; console strings stay ASCII-safe
# (um / deg) so a GBK Windows console can print them.
TEXTS = {
    "zh": {
        # figure
        "title": "打线弧（走线平面内的剖面，绝对坐标）",
        "label_x": "X（从 A 点水平向右，µm）",
        "label_y": "Y（从 A 点水平面向上，µm）",
        "legend_curve": "中心线（样条插值）",
        "legend_points": "控制点 {names}（共 {count} 个）",
        "ae_line": "A–E 连线（焊盘中心连线）",
        "level": "A 点水平面",
        "peak_height": "最高控制点\n（相对 A 的高度）{h:.0f} µm",
        "rise": "出线角 {a:.1f}°（水平）\nAB = {lead:.0f} µm",
        "fall": "落线角 {a:.1f}°（水平）\nED = {lead:.0f} µm",
        "peak": "弧线控制点 {n}\n({x:.0f}, {y:.0f}) µm",
        "caption": ("A–E 水平距离 {span:.0f} µm ｜ A–E 高度差 {height:.0f} µm ｜ "
                    "最高控制点 {peak:.0f} µm（相对 A）｜ 出线/落线 {rise:.1f}°/{fall:.1f}°"
                    "（水平基准）｜ 进出线 {lead:.0f} µm ｜ 线径 {dia:.0f} µm ｜ "
                    "共 {count} 个控制点"),
        # console
        "warn_span": "警告: SPAN 必须大于 0; 已改用 1 um。",
        "warn_ratio": "警告: 控制点 {index} (ratio={ratio:.3f}) 超出 0..1; 已夹紧。",
        "warn_font": "警告: 未找到中文字体, 图中的中文可能显示为方框。",
        "h_params": "=== 弧线参数 ===",
        "l_span": "   水平跨度 X       {value:8.1f} um   (A -> E 的水平距离)",
        "l_height": "   A-E 高度差       {value:8.1f} um   (E 相对 A; 正 = E 更高)",
        "l_epos": "   E 点坐标         ({x:7.2f}, {y:7.2f}) um",
        "l_lead": "   进出线距离       {value:8.1f} um   (AB = ED)",
        "l_angles": "   出线 / 落线      {rise:8.1f} / {fall:.1f} deg   (以水平面为基准)",
        "l_points": "   弧线控制点       {count} 个   (比例 -> 绝对坐标)",
        "l_point_row": "     C{n:<2} 比例 {ratio:6.3f} -> x {x:7.2f} um  y {y:7.2f} um",
        "h_points": "=== 控制点 (um), 共 {count} 个, 绝对 X/Y ===",
        "row": "   {name:<4} ({x:8.2f}, {y:8.2f})",
        "curve_top": "   曲线最高点 y    {top:8.2f} um (最高控制点 {peak:.1f} um, {dev:+.1f}%)",
        "measured_rise": "   实测出线角 (水平) {value:.2f} deg   [设定 {requested:.1f}]",
        "measured_fall": "   实测落线角 (水平) {value:.2f} deg   [设定 {requested:.1f}, 下降]",
        "ab_ed": "   |AB| {ab:.1f} um | |ED| {ed:.1f} um",
        "saved": "已保存: {path}",
    },
    "en": {
        # figure
        "title": "Wire bond loop (section in the wire plane, absolute coordinates)",
        "label_x": "X (horizontal, from A towards E, µm)",
        "label_y": "Y (height above A's level, µm)",
        "legend_curve": "Centreline (spline interpolation)",
        "legend_points": "Control points {names} ({count} total)",
        "ae_line": "A-E line (pad centres)",
        "level": "A's horizontal plane",
        "peak_height": "highest control point\n(height above A) {h:.0f} µm",
        "rise": "rise angle {a:.1f}° (horizontal)\nAB = {lead:.0f} µm",
        "fall": "fall angle {a:.1f}° (horizontal)\nED = {lead:.0f} µm",
        "peak": "loop control point {n}\n({x:.0f}, {y:.0f}) µm",
        "caption": ("A-E horizontal distance {span:.0f} µm | A-E height difference "
                    "{height:.0f} µm | highest control point {peak:.0f} µm (above A) | "
                    "rise/fall {rise:.1f}°/{fall:.1f}° (horizontal) | lead {lead:.0f} µm | "
                    "wire {dia:.0f} µm | {count} control points"),
        # console
        "warn_span": "WARNING: SPAN must be positive; using 1 um.",
        "warn_ratio": "WARNING: loop point {index} (ratio={ratio:.3f}) is outside "
                      "0..1; clamped.",
        "warn_font": "WARNING: no CJK font found; Chinese glyphs may not render.",
        "h_params": "=== loop parameters ===",
        "l_span": "   span X (A->E)    {value:8.1f} um   (horizontal distance)",
        "l_height": "   height diff      {value:8.1f} um   (E relative to A; + = E higher)",
        "l_epos": "   E position       ({x:7.2f}, {y:7.2f}) um",
        "l_lead": "   lead distance    {value:8.1f} um   (AB = ED)",
        "l_angles": "   rise / fall      {rise:8.1f} / {fall:.1f} deg   (from the HORIZONTAL plane)",
        "l_points": "   loop points      {count}   (ratio -> absolute)",
        "l_point_row": "     C{n:<2} ratio {ratio:6.3f} -> x {x:7.2f} um  y {y:7.2f} um",
        "h_points": "=== control points (um), {count} points, absolute X/Y ===",
        "row": "   {name:<4} ({x:8.2f}, {y:8.2f})",
        "curve_top": "   curve top y      {top:8.2f} um (highest control point "
                     "{peak:.1f} um, {dev:+.1f}%)",
        "measured_rise": "   measured rise (horizontal) {value:.2f} deg   "
                         "[requested {requested:.1f}]",
        "measured_fall": "   measured fall (horizontal) {value:.2f} deg   "
                         "[requested {requested:.1f}, descending]",
        "ab_ed": "   |AB| {ab:.1f} um | |ED| {ed:.1f} um",
        "saved": "saved: {path}",
    },
}

#: languages in the order ``--lang both`` uses
LANGUAGES = ("zh", "en")

# ======================================================================
# geometry
# ======================================================================

MAX_ANGLE = 90.0                # stay just short of vertical, so B / D keep an X offset
MIN_POINT_GAP = 0.002           # minimum X gap between loop points, fraction of the span


def _spread_positions(values, gap, low, high):
    """Return ``values`` as strictly increasing positions with a minimum gap.

    The result stays inside ``[low, high]``; when the points cannot all fit with
    ``gap`` the gap is reduced so that they do - the interpolation needs strictly
    increasing parameters.
    """
    count = len(values)
    if count == 0:
        return []
    if high <= low:
        high = low + max(float(gap), 1e-9)
    span = high - low
    step = float(gap)
    if count > 1 and step * (count - 1) > span:
        step = span / float(count - 1)
    result = []
    for index, value in enumerate(values):
        lower = float(low) if index == 0 else result[-1] + step
        upper = float(high) - (count - 1 - index) * step
        if upper < lower:
            upper = lower
        result.append(min(max(float(value), lower), upper))
    return result


def loop_profile(end_x, end_y, loop_points, rise_angle, fall_angle, lead_distance):
    """Return the ``4 + N`` control points A, B, [N loop points], D, E.

    Every point is an absolute ``(x, y)`` pair in micrometres: X to the right from
    A, Y upwards from A's level.

    ==============  =======================================================
    point           position
    ==============  =======================================================
    A               ``(0, 0)``
    B               ``(lead * cos(rise), lead * sin(rise))``
    loop point i    ``(ratio_i * end_x, y_i)`` - ratio along the span, y absolute
    D               ``(end_x - lead*cos(fall), end_y + lead*sin(fall))``
    E               ``(end_x, end_y)``
    ==============  =======================================================

    ``rise_angle`` / ``fall_angle`` are measured from the horizontal plane, so
    ``B`` and ``D`` keep those angles no matter what ``HEIGHT`` does to the A-E
    line. Each loop point is given as ``(ratio, y)``: ``ratio`` is the position
    along the A-E span (0 = A, 1 = E) and ``y`` is the absolute height. The
    points are sorted by X and clamped inside ``(0, end_x)`` with a minimum gap;
    the horizontal reach of each lead is then clamped so B stays before the first
    loop point and D after the last one (strictly increasing X).
    """
    end_x = float(end_x)
    end_y = float(end_y)
    points = sorted((float(ratio) * end_x, float(y)) for ratio, y in loop_points)

    lead = float(lead_distance)
    rise = math.radians(min(max(float(rise_angle), 0.0), MAX_ANGLE))
    fall = math.radians(min(max(float(fall_angle), 0.0), MAX_ANGLE))

    margin = max(end_x, 1.0) * 1e-4
    gap = max(end_x, 1.0) * MIN_POINT_GAP
    positions = _spread_positions([x for x, _y in points], gap,
                                 margin, end_x - margin)
    interior = [(positions[i], points[i][1]) for i in range(len(points))]

    du_b = lead * math.cos(rise)
    du_d = lead * math.cos(fall)
    if interior:
        if interior[0][0] > 0.0:
            du_b = min(du_b, interior[0][0] * 0.98)
        room = end_x - interior[-1][0]
        if room > 0.0:
            du_d = min(du_d, room * 0.98)
    else:
        du_b = min(du_b, end_x * 0.49)
        du_d = min(du_d, end_x * 0.49)

    profile = [
        (0.0, 0.0),                                             # A
        (du_b, lead * math.sin(rise)),                          # B
    ]
    profile.extend(interior)                                    # the loop points
    profile.append((end_x - du_d, end_y + lead * math.sin(fall)))   # D
    profile.append((end_x, end_y))                              # E
    return profile


def sample_curve(points2d, samples=600):
    """Sample the interpolating B-spline built from ``points2d``.

    Chord-length parameterised natural cubic spline, the same model as
    ``Part.BSplineCurve.interpolate()``.
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


def control_point_labels(count):
    """Labels for a ``4 + N`` point profile: A B [C | C1 C2 ...] D E."""
    interior = max(count - 4, 0)
    if interior <= 1:
        middle = ["C"] if interior == 1 else []
    else:
        middle = ["C%d" % (i + 1) for i in range(interior)]
    return ["A", "B"] + middle + ["D", "E"]


# ======================================================================
# build the loop (language independent)
# ======================================================================

def build_data():
    """Compute every geometric quantity the drawing and the report need."""
    end_x = float(SPAN)             # SPAN is the horizontal (X) distance A -> E
    end_y = float(HEIGHT)           # HEIGHT is E's height relative to A

    warnings = []
    if end_x <= 0.0:
        warnings.append(("warn_span", {}))
        end_x = 1.0

    # a loop point outside 0..1 of the span would be pushed onto the border: say so
    for index, (ratio, _y) in enumerate(LOOP_POINTS):
        if not 0.0 < float(ratio) < 1.0:
            warnings.append(("warn_ratio",
                             {"index": index + 1, "ratio": float(ratio)}))

    profile = loop_profile(end_x, end_y, LOOP_POINTS, RISE_ANGLE, FALL_ANGLE,
                           LEAD_DISTANCE)
    xs, ys = sample_curve(profile)
    names = control_point_labels(len(profile))

    # among the loop points (the interior ones) pick the highest, for the callout;
    # with no loop point at all the highest of A-E is used instead
    if len(profile) > 4:
        peak_index = max(range(2, len(profile) - 2), key=lambda i: profile[i][1])
    else:
        peak_index = max(range(len(profile)), key=lambda i: profile[i][1])
    peak_x = profile[peak_index][0]
    peak_y = profile[peak_index][1]

    curve_top = float(np.max(ys))
    b_x, b_y = profile[1]
    d_x, d_y = profile[-2]
    e_x, e_y = profile[-1]

    return {
        "end_x": end_x,
        "end_y": end_y,
        "lead": float(LEAD_DISTANCE),
        "loop_points": list(LOOP_POINTS),
        "profile": profile,
        "names": names,
        "xs": xs,
        "ys": ys,
        "peak_index": peak_index,
        "peak_x": peak_x,
        "peak_y": peak_y,
        "curve_top": curve_top,
        "curve_dev": ((curve_top / peak_y - 1.0) * 100.0) if peak_y else 0.0,
        "rise_display": min(max(float(RISE_ANGLE), 0.0), MAX_ANGLE),
        "fall_display": min(max(float(FALL_ANGLE), 0.0), MAX_ANGLE),
        "measured_rise": math.degrees(math.atan2(b_y, b_x)),
        "measured_fall": math.degrees(math.atan2(e_y - d_y, e_x - d_x)),
        "ab": math.hypot(b_x, b_y),
        "ed": math.hypot(e_x - d_x, e_y - d_y),
        "warnings": warnings,
    }


# ======================================================================
# console output
# ======================================================================

def emit(lines):
    """Print a block of lines, surviving a console that cannot encode them.

    A GBK Windows console cannot print every character (for instance the em
    dash); instead of crashing we re-encode with ``errors="replace"``.
    """
    text = "\n".join(lines)
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding, "replace"))


def warning_lines(data, lang):
    """Translated warning messages for the given language."""
    tx = TEXTS[lang]
    return [tx[key].format(**kwargs) for key, kwargs in data["warnings"]]


def report_lines(data, lang):
    """The console report, translated into ``lang``."""
    tx = TEXTS[lang]
    out = warning_lines(data, lang)
    if out:
        out.append("")

    out.append(tx["h_params"])
    out.append(tx["l_span"].format(value=data["end_x"]))
    out.append(tx["l_height"].format(value=data["end_y"]))
    out.append(tx["l_epos"].format(x=data["end_x"], y=data["end_y"]))
    out.append(tx["l_lead"].format(value=data["lead"]))
    out.append(tx["l_angles"].format(rise=data["rise_display"],
                                     fall=data["fall_display"]))
    out.append(tx["l_points"].format(count=len(data["loop_points"])))
    for index, (ratio, y) in enumerate(sorted(data["loop_points"])):
        out.append(tx["l_point_row"].format(
            n=index + 1, ratio=float(ratio),
            x=float(ratio) * data["end_x"], y=float(y)))

    out.append("")
    out.append(tx["h_points"].format(count=len(data["profile"])))
    for name, (x, y) in zip(data["names"], data["profile"]):
        out.append(tx["row"].format(name=name, x=x, y=y))

    out.append("")
    out.append(tx["curve_top"].format(top=data["curve_top"], peak=data["peak_y"],
                                      dev=data["curve_dev"]))
    out.append(tx["measured_rise"].format(value=data["measured_rise"],
                                          requested=data["rise_display"]))
    out.append(tx["measured_fall"].format(value=data["measured_fall"],
                                          requested=data["fall_display"]))
    out.append(tx["ab_ed"].format(ab=data["ab"], ed=data["ed"]))
    return out


# ======================================================================
# drawing
# ======================================================================

def configure_font(lang):
    """Select a font able to render the annotations of ``lang``.

    English needs only Latin glyphs, so matplotlib's bundled DejaVu Sans is
    always enough; Chinese needs a CJK font. Returns ``False`` when a CJK font
    was required but none was found (the caller then prints a warning).
    """
    if lang == "en":
        plt.rcParams["font.sans-serif"] = [FALLBACK_FONT]
        plt.rcParams["axes.unicode_minus"] = False
        return True

    available = {f.name for f in font_manager.fontManager.ttflist}
    for candidate in FONT_CANDIDATES:
        if candidate in available:
            plt.rcParams["font.sans-serif"] = [candidate]
            plt.rcParams["axes.unicode_minus"] = False
            return True

    plt.rcParams["font.sans-serif"] = [FALLBACK_FONT]
    plt.rcParams["axes.unicode_minus"] = False
    return False


def draw(data, lang, out_path, dpi=FIG_DPI):
    """Write the loop figure with the annotations of ``lang``; returns the path."""
    tx = TEXTS[lang]
    font_ok = configure_font(lang)

    fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=dpi)
    fig.subplots_adjust(left=0.10, right=0.97, top=0.92, bottom=0.16)

    cx = [p[0] for p in data["profile"]]
    cy = [p[1] for p in data["profile"]]
    end_x, end_y = data["end_x"], data["end_y"]

    ax.plot(data["xs"], data["ys"], color=COLOUR_CURVE, linewidth=LW_CURVE,
            solid_capstyle="round", zorder=3, label=tx["legend_curve"])
    ax.plot(cx, cy, "o", color=COLOUR_POINTS, markersize=MARKER_SIZE, zorder=4,
            label=tx["legend_points"].format(names=" ".join(data["names"]),
                                             count=len(data["profile"])))
    ax.plot(cx, cy, color=COLOUR_POINTS, linewidth=1.0, linestyle=(0, (1, 2)),
            zorder=4)

    # reference lines: the A-E line and the level plane through A
    ax.plot([0.0, end_x], [0.0, end_y], linestyle=(0, (6, 4)), color=COLOUR_GUIDE,
            linewidth=LW_GUIDE, zorder=2, label=tx["ae_line"])
    ax.plot([0.0, LEVEL_REF_LENGTH], [0.0, 0.0], linestyle=(0, (2, 3)),
            color="#B0B0B0", linewidth=LW_GUIDE, zorder=1, label=tx["level"])
    ax.text(LEVEL_REF_LENGTH, -YLIM_MARGIN_BOTTOM * 0.45, tx["level"],
            fontsize=8.5, color="#909090", ha="right", va="top")

    for name, x, y in zip(data["names"], cx, cy):
        ax.annotate(name, xy=(x, y),
                    xytext=(x + ANN_LABEL_OFFSET[0], y + ANN_LABEL_OFFSET[1]),
                    fontsize=12, fontweight="bold", color=COLOUR_POINTS)

    # the two rays that define B and D (drawn at their horizontal angles)
    ax.plot([0, cx[1]], [0, cy[1]], ":", color=COLOUR_RAY, linewidth=LW_RAY)
    ax.plot([cx[-1], cx[-2]], [cy[-1], cy[-2]], ":", color=COLOUR_RAY,
            linewidth=LW_RAY)

    # highest point: a vertical arrow down to the level plane through A
    ax.annotate("", xy=(data["peak_x"], data["peak_y"]), xytext=(data["peak_x"], 0.0),
                arrowprops=dict(arrowstyle="<->", color=COLOUR_GUIDE, lw=1.1))
    ax.text(data["peak_x"] + PEAK_LABEL_X, data["peak_y"] * PEAK_LABEL_Y,
            tx["peak_height"].format(h=data["peak_y"]), fontsize=10,
            color=COLOUR_GUIDE)

    ax.annotate(tx["rise"].format(a=data["rise_display"], lead=data["lead"]),
                xy=(cx[1], cy[1]),
                xytext=(cx[1] + ANN_RISE_OFFSET[0], cy[1] + ANN_RISE_OFFSET[1]),
                fontsize=10, color=COLOUR_RAY, ha="left",
                arrowprops=dict(arrowstyle="->", color=COLOUR_RAY))
    ax.annotate(tx["fall"].format(a=data["fall_display"], lead=data["lead"]),
                xy=(cx[-2], cy[-2]),
                xytext=(cx[-2] + ANN_FALL_OFFSET[0], cy[-2] + ANN_FALL_OFFSET[1]),
                fontsize=10, color=COLOUR_RAY, ha="left",
                arrowprops=dict(arrowstyle="->", color=COLOUR_RAY))
    if len(data["profile"]) > 4:
        ax.annotate(tx["peak"].format(n=data["peak_index"] - 1,
                                      x=data["peak_x"], y=data["peak_y"]),
                    xy=(data["peak_x"], data["peak_y"]),
                    xytext=(data["peak_x"] + ANN_PEAK_OFFSET[0],
                            data["peak_y"] + ANN_PEAK_OFFSET[1]),
                    fontsize=10, color=COLOUR_CURVE, ha="center",
                    arrowprops=dict(arrowstyle="->", color=COLOUR_CURVE))

    ax.set_title(tx["title"], fontsize=12.5)
    ax.set_xlabel(tx["label_x"])
    ax.set_ylabel(tx["label_y"])
    # limits follow the drawing, so a positive or negative HEIGHT is always framed
    all_x = list(cx) + [0.0, LEVEL_REF_LENGTH]
    all_y = list(cy) + [0.0, end_y]
    ax.set_xlim(min(all_x) - XLIM_MARGIN_LEFT, max(all_x) + XLIM_MARGIN_RIGHT)
    ax.set_ylim(min(all_y) - YLIM_MARGIN_BOTTOM, max(all_y) + YLIM_MARGIN_TOP)
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    # ax.legend(loc="upper right", fontsize=9.5)
    ax.set_aspect("equal", adjustable="box")

    fig.text(0.5, 0.035,
             tx["caption"].format(span=SPAN, height=float(HEIGHT),
                                  peak=data["peak_y"],
                                  rise=data["rise_display"],
                                  fall=data["fall_display"],
                                  lead=data["lead"], dia=WIRE_DIAMETER,
                                  count=len(data["profile"])),
             ha="center", fontsize=10.0, color="#333333")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return font_ok


# ======================================================================
# command line
# ======================================================================

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="wirebond_sketch.py",
        description=("Draw the wire bond loop from the parameters in this file. "
                     "The console report and the figure annotations are bilingual; "
                     "pick them with --lang. / 按本文件顶部的参数绘制打线弧剖面图, "
                     "报告与图注支持中英双语, 用 --lang 选择。"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("examples:\n"
                "  python scripts/wirebond_sketch.py\n"
                "  python scripts/wirebond_sketch.py --lang en\n"
                "  python scripts/wirebond_sketch.py --lang both\n"
                "  python scripts/wirebond_sketch.py -o data/my_loop.png\n"))
    parser.add_argument("-l", "--lang", choices=("zh", "en", "both"), default="zh",
                        help="language of the report and the annotations: "
                             "zh = Chinese, en = English, both = print both "
                             "reports and write two figures (default: zh)")
    parser.add_argument("-o", "--output", default=None,
                        help="output PNG, relative to the repository root "
                             "(default: wirebond-sketch-{lang}.png; with --lang both the suffixes "
                             "_zh / _en are inserted)")
    parser.add_argument("-d", "--dpi", type=float, default=FIG_DPI,
                        help="figure resolution (default: %g)" % FIG_DPI)
    return parser.parse_args(argv)


def resolve_outputs(lang, output):
    """Map each language to the PNG it is written to."""
    output = output or os.path.join("src", f"wirebond-sketch-{lang}.png")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if lang == "both":
        base, ext = os.path.splitext(output)
        return {code: os.path.join(root, "%s_%s%s" % (base, code, ext))
                for code in LANGUAGES}
    return {lang: os.path.join(root, output)}


def main(argv=None):
    # A Windows console is often cp936: reconfiguring to UTF-8 keeps the Chinese
    # report readable instead of producing mojibake.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args(argv)
    lang = args.lang
    langs = LANGUAGES if lang == "both" else (lang,)
    outputs = resolve_outputs(lang, args.output)

    data = build_data()

    for index, code in enumerate(langs):
        if index:
            print("")
        emit(report_lines(data, code))
        font_ok = draw(data, code, outputs[code], dpi=args.dpi)
        print(TEXTS[code]["saved"].format(path=outputs[code]))
        if not font_ok:
            print(TEXTS[code]["warn_font"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

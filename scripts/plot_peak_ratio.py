# -*- coding: utf-8 -*-
"""Plot the wire loop shape for several ``PeakRatio`` values.

The curve is generated with exactly the same control point formulas as
``src/WireBonder/core.py`` (``loop_profile``) and then smoothed with a natural
cubic spline, standing in for FreeCAD's ``Part.BSplineCurve.interpolate()``.

Output: docs/images/peak-ratio.png

Run:  python scripts/plot_peak_ratio.py
"""

import os

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager

# ----------------------------------------------------------------------
# style: use a font that actually has Chinese glyphs, when available
# ----------------------------------------------------------------------
_available = {f.name for f in font_manager.fontManager.ttflist}
for _candidate in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun"):
    if _candidate in _available:
        plt.rcParams["font.sans-serif"] = [_candidate]
        break
plt.rcParams["axes.unicode_minus"] = False


# ----------------------------------------------------------------------
# geometry: identical formulas to core.loop_profile()
# ----------------------------------------------------------------------
# Shape factors, kept in sync with src/WireBonder/core.py. The loop has seven
# control points: the peak plus three on each side.
RISE_POSITION = 0.12
MID_RISE_POSITION = 0.50
MID_RISE_HEIGHT = 0.92
DESCENT_POSITION = 0.38
DESCENT_HEIGHT = 0.86
FALL_POSITION = 0.78


def loop_profile(length, clearance, peak_ratio,
                 rise_ratio=0.60, fall_ratio=0.20):
    """Return the seven control points ``[(u, v), ...]`` of the wire loop."""
    ratio = min(max(float(peak_ratio), 0.05), 0.95)
    peak_u = length * ratio
    tail = length - peak_u
    return [
        (0.0, 0.0),                                           # C1
        (RISE_POSITION * peak_u, min(1.0, rise_ratio) * clearance),
        (MID_RISE_POSITION * peak_u, MID_RISE_HEIGHT * clearance),
        (peak_u, clearance),                                  # loop peak
        (peak_u + DESCENT_POSITION * tail, DESCENT_HEIGHT * clearance),
        (peak_u + FALL_POSITION * tail,
         min(0.6, fall_ratio * 2.0) * clearance),
        (length, 0.0),                                        # C2
    ]


def _natural_cubic_coeffs(t, values):
    """Second-derivative form of the natural cubic spline through (t, values).

    Returns ``(b, c, d)`` so that on segment ``j`` with ``dt = t - t[j]``

        value(dt) = values[j] + b[j]*dt + c[j]*dt**2 + d[j]*dt**3

    The system is symmetric tridiagonal with zero end curvature, solved with the
    Thomas algorithm (no SciPy dependency).
    """
    t = np.asarray(t, dtype=float)
    values = np.asarray(values, dtype=float)
    n = len(t) - 1
    h = np.diff(t)

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


def _eval_cubic_spline(t, values, coeffs, positions):
    """Evaluate the spline defined by ``coeffs`` at the given parameter values."""
    b, c, d = coeffs
    n = len(t) - 1
    out = np.empty_like(positions)
    for k, value in enumerate(positions):
        j = max(0, min(n - 1, np.searchsorted(t, value, side="right") - 1))
        dt = value - t[j]
        out[k] = values[j] + b[j] * dt + c[j] * dt ** 2 + d[j] * dt ** 3
    return out


def parametric_spline(u, v, samples=600):
    """Smooth a polyline through its points, the way FreeCAD does it.

    ``Part.BSplineCurve.interpolate()`` interpolates the x and y coordinates
    *independently* against a parameter, rather than treating y as a function of
    x. That matters here: interpolating ``v(u)`` directly makes the spline
    overshoot above the highest control point between two samples, which would
    wrongly suggest that the wire rises above the clearance. Fitting both
    coordinates against the chord-length parameter reproduces the intended loop
    shape, with the peak exactly at ``clearance``.

    IMPORTANT: call this with **real millimetre coordinates**, never with
    pre-normalised ones. The chord-length parameter is built from the actual
    distances between control points, so it depends on how the two axes are
    scaled. Fitting normalised (u/L, v/H) data distorts that parameter and makes
    the end of the loop swing *past* C2 (measured: u/L reaching 1.018 instead of
    1.000, with the tangent turning outward at the landing point). Fitting the
    real geometry first and normalising the result afterwards reproduces the
    plugin's geometry exactly.
    """
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)

    # chord-length parameterisation (the default used by FreeCAD)
    seg = np.hypot(np.diff(u), np.diff(v))
    t = np.concatenate(([0.0], np.cumsum(seg)))
    t /= t[-1]

    xu = _eval_cubic_spline(t, u, _natural_cubic_coeffs(t, u),
                            np.linspace(0.0, 1.0, samples))
    yv = _eval_cubic_spline(t, v, _natural_cubic_coeffs(t, v),
                            np.linspace(0.0, 1.0, samples))
    return xu, yv


def smooth_normalised(length, clearance, ratio, samples=600):
    """Return the loop shape in normalised coordinates, free of fitting artefacts.

    The spline is fitted in millimetres (as FreeCAD does) and only then divided
    by ``length`` / ``clearance``. Fitting the normalised values directly would
    produce a visible bulge past the second bond point and an outward-angled
    landing; see :func:`parametric_spline`.
    """
    pts = loop_profile(length, clearance, ratio)
    um = np.array([p[0] for p in pts], dtype=float)
    vm = np.array([p[1] for p in pts], dtype=float)

    u_mm, v_mm = parametric_spline(um, vm, samples=samples)
    return u_mm / length, v_mm / clearance


# ----------------------------------------------------------------------
# figure
# ----------------------------------------------------------------------
RATIOS = [0.20, 0.42, 0.60, 0.80]
LENGTH = 2.0        # centroid distance (mm) - value only affects the mm labels
CLEARANCE = 0.5     # 500 um

COLOR_HL = "#C0392B"      # highlighted curve
COLOR_GHOST = "#B0B7BF"   # reference curves
COLOR_PT = "#2C3E50"      # control points

fig, axes = plt.subplots(2, 2, figsize=(12, 8.6), dpi=150)
fig.suptitle(
    "拱顶位置比例 PeakRatio 对打线弧形状的影响\n"
    r"（归一化坐标：横轴 $u/L$，纵轴 $v/H$；$L$=质心间距，$H$=净空高度）",
    fontsize=13,
)

for ax, ratio in zip(axes.ravel(), RATIOS):
    # ghost curves for the other ratios, to compare at a glance
    for other in RATIOS:
        if other == ratio:
            continue
        gx, gy = smooth_normalised(LENGTH, CLEARANCE, other)
        ax.plot(gx, gy, color=COLOR_GHOST, linewidth=1.3, linestyle="--",
                zorder=1)

    pts = loop_profile(LENGTH, CLEARANCE, ratio)
    u = np.array([p[0] for p in pts]) / LENGTH
    v = np.array([p[1] for p in pts]) / CLEARANCE
    x, y = smooth_normalised(LENGTH, CLEARANCE, ratio)

    as_default = "（默认）" if abs(ratio - 0.42) < 1e-9 else ""
    ax.plot(x, y, color=COLOR_HL, linewidth=2.6, zorder=3)
    ax.plot(u, v, "o", color=COLOR_PT, markersize=5, zorder=4)

    # mark the loop peak: dotted guide line + a marker with a short caption
    peak_u = ratio
    ax.axvline(peak_u, color=COLOR_HL, linewidth=0.9, linestyle=":", zorder=2)
    ax.plot([peak_u], [1.0], "D", color=COLOR_HL, markersize=6, zorder=5)
    ax.text(peak_u, 1.035, "弧顶", fontsize=9, color=COLOR_HL,
            ha="center", va="bottom")

    # the two bond points
    ax.plot([0.0], [0.0], "s", color="#1F77B4", markersize=7, zorder=5)
    ax.plot([1.0], [0.0], "s", color="#FF7F0E", markersize=7, zorder=5)
    ax.text(0.02, 0.04, "C1 第一焊点", fontsize=8.5, color="#1F77B4")
    ax.text(0.98, 0.04, "C2 第二焊点", fontsize=8.5, color="#FF7F0E",
            ha="right")

    ax.set_title(
        "PeakRatio = {:.2f}{}    弧顶 $u/L$ = {:.2f}，下降段 = {:.2f}$L$".format(
            ratio, as_default, peak_u, 1.0 - peak_u
        ),
        fontsize=11,
    )
    ax.set_xlabel(r"$u / L$（沿质心连线的归一化距离）")
    ax.set_ylabel(r"$v / H$（相对连线的归一化高度）")
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.06, 1.14)
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)

# One figure level legend: every subplot shows the same series, so per-axes
# legends would only collide with the curves.
handles = [
    plt.Line2D([], [], color=COLOR_HL, linewidth=2.6,
               label="当前比例的弧线"),
    plt.Line2D([], [], color=COLOR_GHOST, linewidth=1.3, linestyle="--",
               label="其它比例的参考曲线"),
    plt.Line2D([], [], color=COLOR_PT, marker="o", linestyle="none",
               markersize=5, label="7 个控制点"),
    plt.Line2D([], [], color=COLOR_HL, marker="D", linestyle="none",
               markersize=6, label="弧顶"),
]
fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=9.5,
           frameon=False, bbox_to_anchor=(0.5, 0.075))

fig.text(
    0.5, 0.048,
    "PeakRatio 只把最高点沿连线左右移动，弧顶高度恒等于净空高度 H，两个端点位置不变。",
    ha="center", va="center", fontsize=9.5, color="#444444",
)
fig.text(
    0.5, 0.022,
    "曲线由与 core.loop_profile() 完全相同的 7 个控制点（弧顶 + 左右各 3 个）"
    "做弦长参数化样条插值而成，在真实毫米坐标下拟合后归一化，与 FreeCAD 的实际几何一致。",
    ha="center", va="center", fontsize=8.5, color="#888888",
)
fig.tight_layout(rect=(0, 0.115, 1, 0.94))

out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "images")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "peak-ratio.png")
fig.savefig(out_path)
plt.close(fig)
print("saved:", out_path)

# ----------------------------------------------------------------------
# print the numbers that go into the documentation table
# ----------------------------------------------------------------------
print("\nratio | peak_u (mm) | peak_u/L | tail (mm) | tail/L")
for ratio in RATIOS:
    pts = loop_profile(LENGTH, CLEARANCE, ratio)
    peak = pts[3][0]
    print("  %.2f | %10.3f | %8.0f%% | %9.3f | %7.0f%%"
          % (ratio, peak, ratio * 100, LENGTH - peak, (1 - ratio) * 100))

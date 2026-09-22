"""在三维空间中绘制两个水平放置的 1 cm^2 正方形平面。

几何设定 (单位: cm):
    平面 A: 中心 (0, 0, 0)        水平放置 (法向沿 +Z)
    平面 B: 中心 (10, 0, 2)       水平放置 (法向沿 +Z)
    平面 C: 过 A、B 两个中心连线的铅垂平面 (y = 0),
            它垂直于两个水平正方形, 并把它们各切成两半

    - 平面 A 与平面 B 的水平间距 = 10 cm  (沿 X 轴)
    - 平面 A 与平面 B 的高低落差 = 2 cm   (沿 Z 轴)
    - 每个平面都是 1 cm x 1 cm 的正方形 => 面积 1 cm^2
    - 平面 C 内有一条样条曲线连接两个正方形的中心, 曲线形态仿照打线机
      (wire bonder) 打出的焊线弧: 起点陡升 -> 顶部拱起 -> 平缓落回终点

输出: two_horizontal_squares.png
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")  # 无 GUI 环境下也能导出图片

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# ----------------------------------------------------------------------
# 参数
# ----------------------------------------------------------------------
EDGE = 1.0        # 正方形边长 (cm) -> 面积 1 cm^2
PLANE_GAP = 10.0  # 两个平面的水平间距 (cm)
HEIGHT_DROP = 2.0  # 两个平面的高低落差 (cm)

CENTER_A = np.array([0.0, 0.0, 0.0])
CENTER_B = np.array([PLANE_GAP, 0.0, HEIGHT_DROP])

# 铅垂平面 C 的绘制范围 (它是 y = 0 平面上的一块矩形)
VPLANE_X_MIN = CENTER_A[0] - 1.5
VPLANE_X_MAX = CENTER_B[0] + 1.5
VPLANE_Z_MIN = CENTER_A[2] - 1.8
VPLANE_Z_MAX = CENTER_B[2] + 1.8

# 打线机焊线 (wire loop) 的样条控制点, 全部位于平面 C 内 (y = 0)。
# 起点与终点分别是平面 A、B 的中心; 中间控制点让线先陡升、
# 形成一个拱顶后再平缓落下, 这就是打线机走线的典型轮廓。
WIRE_CTRL_POINTS = np.array(
    [
        [0.00, 0.0, 0.00],   # 第一焊点: 平面 A 的中心
        [0.18, 0.0, 0.85],   # 出线: 几乎垂直抬升 (打线机的起弧)
        [1.60, 0.0, 2.25],
        [4.00, 0.0, 2.95],   # 拱顶 (loop peak)
        [7.00, 0.0, 2.88],
        [9.35, 0.0, 2.42],
        [9.88, 0.0, 2.10],
        [10.00, 0.0, 2.00],  # 第二焊点: 平面 B 的中心
    ],
    dtype=float,
)


def horizontal_square(center, edge=EDGE):
    """返回一个水平正方形 (位于 z = 常数的平面内) 的 4 个顶点。"""
    cx, cy, cz = center
    half = edge / 2.0
    return np.array(
        [
            [cx - half, cy - half, cz],
            [cx + half, cy - half, cz],
            [cx + half, cy + half, cz],
            [cx - half, cy + half, cz],
        ],
        dtype=float,
    )


def catmull_rom_spline(points, samples_per_segment=60):
    """Catmull-Rom 样条: 生成的曲线精确穿过每一个控制点。

    参数化的平滑插值正是描述"打线机走线轨迹"最常用的方式 ——
    给定若干必经点, 得到一条连续且平滑的曲线。
    """
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return pts

    # 首尾各镜像一个虚拟点, 用来确定两端处的切线方向
    head = 2.0 * pts[0] - pts[1]
    tail = 2.0 * pts[-1] - pts[-2]
    ext = np.vstack([head, pts, tail])

    t = np.linspace(0.0, 1.0, samples_per_segment, endpoint=False)[:, None]
    segments = []
    for i in range(len(ext) - 3):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        segments.append(
            0.5
            * (
                2.0 * p1
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t**2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t**3
            )
        )
    return np.vstack(segments + [pts[-1][None, :]])


# ----------------------------------------------------------------------
# 绘图
# ----------------------------------------------------------------------
fig = plt.figure(figsize=(11, 8), dpi=200)
ax = fig.add_subplot(111, projection="3d")

# 两个正方形平面
verts_a = horizontal_square(CENTER_A)
verts_b = horizontal_square(CENTER_B)

face_a = Poly3DCollection(
    [verts_a], facecolor="#4C8BF5", edgecolor="#123E8C", linewidth=1.4, alpha=0.85
)
face_b = Poly3DCollection(
    [verts_b], facecolor="#F5674C", edgecolor="#8C2912", linewidth=1.4, alpha=0.85
)
face_a.set_zorder(3)  # 两个正方形绘制在竖直平面之上, 避免颜色被覆盖
face_b.set_zorder(3)
ax.add_collection3d(face_a)
ax.add_collection3d(face_b)

# 平面 C: 过两个正方形中心连线的铅垂平面 (y = 0)
verts_c = np.array(
    [
        [VPLANE_X_MIN, 0.0, VPLANE_Z_MIN],
        [VPLANE_X_MAX, 0.0, VPLANE_Z_MIN],
        [VPLANE_X_MAX, 0.0, VPLANE_Z_MAX],
        [VPLANE_X_MIN, 0.0, VPLANE_Z_MAX],
    ],
    dtype=float,
)
face_c = Poly3DCollection(
    [verts_c], facecolor="#34A853", edgecolor="#14603A", linewidth=1.6, alpha=0.15
)
face_c.set_zorder(1)
ax.add_collection3d(face_c)

# 注: 样条曲线与焊点的绘制统一放在文件末尾 (所有平面之后),
#     以保证线不会被平面 A / B 遮挡

ax.text(
    VPLANE_X_MIN + 0.4,
    0.0,
    VPLANE_Z_MAX + 0.15,
    "Plane C\n(vertical, through the two centers)",
    color="#14603A",
    ha="left",
    va="bottom",
    fontsize=10,
)

# 注: 两个焊点同样在文件末尾与曲线一起绘制

# 标注水平间距 10 cm
ax.plot(
    [CENTER_A[0], CENTER_B[0]],
    [CENTER_A[1], CENTER_B[1]],
    [CENTER_A[2], CENTER_A[2]],
    color="#2E7D32",
    linestyle="--",
    linewidth=1.4,
)
ax.text(
    (CENTER_A[0] + CENTER_B[0]) / 2,
    CENTER_A[1],
    CENTER_A[2] - 0.45,
    "gap = 10 cm",
    color="#2E7D32",
    ha="center",
    va="top",
    fontsize=10,
)

# 标注高低落差 2 cm
ax.plot(
    [CENTER_B[0], CENTER_B[0]],
    [CENTER_B[1], CENTER_B[1]],
    [CENTER_A[2], CENTER_B[2]],
    color="#6A1B9A",
    linestyle="--",
    linewidth=1.4,
)
ax.text(
    CENTER_B[0] + 0.25,
    CENTER_B[1],
    (CENTER_A[2] + CENTER_B[2]) / 2,
    "height drop = 2 cm",
    color="#6A1B9A",
    ha="left",
    va="center",
    fontsize=10,
)

# 在平面 A 上画出边长 1 cm 的示意标注
ax.text(
    CENTER_A[0],
    CENTER_A[1],
    CENTER_A[2] + 0.45,
    "Plane A\n1 cm$^2$",
    color="#123E8C",
    ha="center",
    va="bottom",
    fontsize=10,
)
ax.text(
    CENTER_B[0],
    CENTER_B[1],
    CENTER_B[2] + 0.45,
    "Plane B\n1 cm$^2$",
    color="#8C2912",
    ha="center",
    va="bottom",
    fontsize=10,
)

# ----------------------------------------------------------------------
# 最后绘制平面 C 内的样条曲线与两个焊点
# 放在所有平面之后绘制, 线就不会被平面 A / B 遮盖
# ----------------------------------------------------------------------
wire = catmull_rom_spline(WIRE_CTRL_POINTS, samples_per_segment=90)

# 用三层描边叠加出金属丝的观感: 暗色外缘 + 金属本体 + 白色高光
for width, color, alpha in (
    (4.6, "#2B2B2B", 0.85),  # 外缘: 金属丝的阴影/氧化边
    (2.6, "#C8CDD4", 1.0),   # 本体: 银灰色金属
    (0.9, "#FFFFFF", 0.9),   # 高光: 让线看起来是有光泽的实心细丝
):
    ax.plot(
        wire[:, 0],
        wire[:, 1],
        wire[:, 2],
        color=color,
        linewidth=width,
        alpha=alpha,
        solid_capstyle="round",
        zorder=10,
    )

ax.text(
    4.6,
    0.0,
    3.18,
    "spline wire (wire-bonding style)",
    color="#4A4A4A",
    ha="center",
    va="bottom",
    fontsize=10,
)

# 曲线两端落在两个正方形的中心, 用金色焊球 (bond ball) 标记这两个焊点。
# 焊点也使用 line + marker 绘制 (而不是 scatter), 这样它们与曲线同批次
# 且添加得更晚, 从而始终绘制在所有平面与线之上。
for center in (CENTER_A, CENTER_B):
    ax.plot(
        [center[0]],
        [center[1]],
        [center[2]],
        marker="o",
        markersize=9,
        markerfacecolor="#C9A227",
        markeredgecolor="#6B4E05",
        markeredgewidth=1.0,
        linestyle="none",
        zorder=11,
    )
    # 焊球上的高光小点, 让它更像金属球
    ax.plot(
        [center[0]],
        [center[1] - 0.07],
        [center[2] + 0.07],
        marker="o",
        markersize=3.5,
        markerfacecolor="#FFF3C4",
        markeredgecolor="none",
        linestyle="none",
        zorder=12,
    )

# 坐标轴设置
ax.set_xlabel("X (cm)")
ax.set_ylabel("Y (cm)")
ax.set_zlabel("Z (cm)")

ax.set_xlim(-2.5, 12.5)
ax.set_ylim(-2.0, 2.0)
ax.set_zlim(-2.2, 4.6)

# 保持三轴等比例，正方形才不会被拉伸成长方形
try:
    ax.set_box_aspect((15.0, 4.0, 6.8))
except AttributeError:  # matplotlib < 3.3
    pass

ax.view_init(elev=18, azim=-62)
ax.set_title(
    "Two horizontal 1 cm$^2$ squares + vertical plane with a wire-bonded spline"
)
ax.grid(True, linestyle=":", linewidth=0.5)

fig.tight_layout()
out_path = "two_horizontal_squares.png"
fig.savefig(out_path, bbox_inches="tight")
plt.close(fig)

print(f"Saved image: {out_path}")
print("Plane A center:", CENTER_A, " Plane B center:", CENTER_B)

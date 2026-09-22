# WireBonder 设计文档（PRD）

> FreeCAD 打线（Wire Bonding）辅助插件 —— 由两个选中平面自动构造平分平面，并在其内生成连接两个质心的金线（打线弧）

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v0.4.0 |
| 日期 | 2026-09-21 |
| 状态 | 已实现并通过实机验证 |
| 源码目录 | [`src/`](../src/README.md) |
| 安装文档 | [`README.md`](../README.md) |
| 插件说明 | [`src/README.md`](../src/README.md) |

---

## 1. 项目概述

### 1.1 背景

在封装与微连接工艺中，**打线（wire bonding）** 用一根极细的金线（典型直径 18–25 µm）把芯片焊盘与基板/引线框架连接起来。金线不是直线，而是被劈刀"打"出一道弧线（loop），以保证线弧在芯片上方有足够的**净空高度（clearance）**、避免与芯片边缘或相邻结构干涉。

做结构设计、热-力仿真或装配评审时，经常需要在三维 CAD 里快速表达这些打线弧：

- 用普通建模方式逐条手画弧线极其耗时；
- 弧线的走向必须落在"两个焊盘中心的连线 + 法线角平分方向"所确定的平面内，手工难以保证；
- 金线直径（20 µm 级）与净空高度都是经常变化的工艺参数，需要随时调整。

本插件把这个过程固化为一次点击：**选中两个平面 → 自动构造平分平面 → 生成金线（可选焊球）**，并把直径、净空高度等做成可实时调整的参数。

### 1.2 目标用户

| 用户 | 典型诉求 |
| --- | --- |
| 封装/微电子结构工程师 | 在 CAD 中快速表达打线布局，检查与壳体、盖板的干涉 |
| 仿真工程师 | 得到可用的金线实体，导入 FEM 做热-力分析 |
| 工艺工程师 | 用参数化模型对比不同线径、不同净空高度的方案 |

### 1.3 设计目标

1. **几何正确**：金线严格落在"质心连线 + 法线角平分"所张成的平面内，且端点精确落在两个面的质心。
2. **参数化**：金线直径、净空高度、弧顶位置等全部可在属性编辑器中调整并自动重建。
3. **工程可用**：可选生成真实直径的金线实体与焊球；默认给出轻量的中心线，兼顾低配机器与快速预览。
4. **不添乱**：插件加载失败不得影响 FreeCAD 启动；构造用辅助面自动隐藏。

---

## 2. 范围

### 2.1 在范围内

- 由两个选中**平面**（任意朝向）构造平分平面与打线弧；
- 金线中心线、金线实体（放样）、两个焊球；
- 参数化对象与参数编辑面板；
- 辅助平面（可显示/隐藏）；
- 加载与排错日志。

### 2.2 不在范围内

- 真实打线工艺参数的物理仿真（金线材质、键合强度、劈刀路径）；
- 多根金线的批量/阵列生成（可重复执行命令实现）；
- 焊盘自身几何的生成（焊盘由用户建模，插件只读取其面）；
- 打线弧的工艺分类（如 BBOS / BSS / SSB 标准 loop profile）。

---

## 3. 术语表

| 术语 | 含义 |
| --- | --- |
| Wire Bonding（打线） | 用细金属丝连接芯片焊盘与外部的工艺 |
| Wire Loop（线弧） | 金线在两点之间形成的弧形结构 |
| Clearance（净空高度） | 本插件中定义为**弧顶相对两质心连线的高度** |
| Bond Ball（焊球） | 第一焊点在焊盘上压出的球状焊点，本插件用球体表示 |
| 平分平面 | 由"两质心连线方向"与"两条质心法线的角平分方向"张成的平面 |
| 辅助面 | 仅用于构造参考的平分平面，生成后自动隐藏 |

---

## 4. 功能需求

| 编号 | 需求 | 优先级 | 状态 |
| --- | --- | --- | --- |
| FR-1 | 用户可选中**恰好两个面**（可来自同一实体或两个实体） | 高 | 已实现 |
| FR-2 | 由两个面自动计算平分平面（质心连线 + 法线角平分） | 高 | 已实现 |
| FR-3 | 在平分平面内生成连接两个质心的打线弧 | 高 | 已实现 |
| FR-4 | 金线直径可设置（默认 20 µm），可放样成实体 | 高 | 已实现 |
| FR-5 | 净空高度可设置（默认 500 µm，面板以 µm 输入） | 高 | 已实现 |
| FR-6 | 弧顶位置、出线陡升、落线姿态比例可设置 | 中 | 已实现 |
| FR-7 | 可选生成两个焊球，球直径可设置（默认 50 µm，约为线径 2.5 倍） | 中 | 已实现 |
| FR-8 | 生成对象为**参数化对象**，改属性自动重建几何 | 高 | 已实现 |
| FR-9 | 平分面作为辅助面，生成后自动隐藏；**默认不创建** | 中 | 已实现 |
| FR-10 | 退化情形（法线反平行、连线与平分线平行等）给出明确提示而非产出错误几何 | 高 | 已实现 |
| FR-11 | 可选只显示中心线（细直径下仍可看清走线） | 中 | 已实现 |
| FR-12 | 生成后可整体删除/重生成，不破坏原有模型 | 中 | 已实现 |
| FR-13 | 选中面来自 `PartDesign::Body` 时给出作用域提示（面板橙色提示 + Report view 中文说明） | 中 | 已实现 |
| FR-14 | 面取自 `App::Part` 容器内的零件时，自动补偿父容器变换，几何始终落在全局装配坐标 | 高 | 已实现（v0.1.2 修复） |
| FR-15 | 面板显示两个面的全局质心与**两质心间距 L**；当净空高度大于 L 时给出提醒 | 中 | 已实现（v0.1.2） |
| FR-16 | **走线平面偏转角**可设置：走线平面绕两质心连线旋转指定角度，默认 `0°` 与原平分平面完全重合 | 中 | 已实现（v0.1.3） |
| FR-17 | **多语言**：界面文字跟随 FreeCAD 语言设置，中文环境显示中文，**其它语言（含英文）显示英文**；未翻译条目回退英文 | 中 | 已实现（v0.2.0） |
| FR-18 | 切换语言**无需重启**：偏好设置改语言后工作台名、工具栏/菜单按钮、面板立即随之切换 | 中 | 已实现（v0.3.0） |
| FR-19 | **面板记住上次设置**：OK 后持久化，下次打开自动回填；提供「恢复默认值」 | 中 | 已实现（v0.4.0） |
| FR-20 | **面板可滚动**：内容超出可用高度时出现垂直滚动条，任何控件不被截断；宽度自适应，不出现横向滚动条 | 中 | 已实现（v0.5.0） |
| FR-21 | **分组可折叠**：选中的平面 / 金线参数 / 输出选项三个分组点击标题即可折叠，折叠状态被记住且独立于「恢复默认值」 | 中 | 已实现（v0.5.0） |
| FR-22 | **参数输入框复用属性视图的控件**（`Gui::QuantitySpinBox`）：可自由切换单位、可输入表达式、滚轮悬停不改变数值 | 中 | 已实现（v0.7.0） |
| FR-23 | **焊点凸起形状可选**：下拉框选择 无 / 球形 / 圆台；面板字段随选择动态显隐 | 中 | 已实现（v0.8.0） |
| FR-24 | **两端形状可独立设置**：起点（C1）与终点（C2）各一个下拉框；面板按两端合并显示所需字段 | 中 | 已实现（v0.9.0） |
| FR-25 | **进出线距离可设置**（默认 10 µm）：用绝对距离定位控制点 2 与 6，使进出线角度只由高度比例与该距离决定，与连线长度解耦 | 中 | 已实现（v0.9.0） |
| FR-26 | **线形贴近真实打线轮廓**（平顶 + 长直下降）：8 个控制点，平顶由 3 点支撑，下降段中间点与两端共线使其成为真正的直线；新增「平顶长度」参数（默认 200 µm） | 高 | 已实现（v0.10.0） |

### 4.1 FR-2 的几何定义（精确表述）

设两个面的质心为 `C1`、`C2`，其单位法线为 `n1`、`n2`：

```
d = normalize(C2 - C1)                     # 质心连线方向
if n1 · n2 < 0:  n2 = -n2                  # 统一到同一半球
b = n1 + n2                                # 法线角平分方向
y = normalize(b - d * (b · d))             # 取垂直于 d 的分量 (Gram-Schmidt)
x = d
z = normalize(x × y)                       # 平分平面法向
```

平分平面 `P` 通过 `C1`，且同时包含 `C2`（因为 `C2 - C1` 沿 `x` 方向）。局部坐标系 `(x, y, z)` 均为单位正交向量，`P` 内的任意点可表示为 `C1 + u·x + v·y`。

**走线平面偏转角 θ（v0.1.3 新增）**：默认 `θ = 0°` 时走线平面就是平分平面 `P`。给定 θ 时把局部 y、z 轴**绕 x 轴（质心连线）**旋转 θ：

```
y' = Rot(x, θ) · y
z' = Rot(x, θ) · z
```

弧顶方向随之改变（高度改为沿 `y'` 计量），金线所在的平面以连线为轴偏转 θ（−180°~180°），可用于绕开障碍或调整进出线方向。由于 θ 只影响 y/z 分量，**两个质心与连线长度保持不变**，`θ = 0` 时与原行为逐位一致。

**典型情形**：两个水平焊盘（`n1 = n2 = +Z`）会得到 `y = +Z`、`z = ±Y` 的**竖直平分平面**，与手工建模时"过两中心连线的铅垂面"完全一致。

### 4.2 FR-3 的打线弧轮廓

弧线在局部坐标下的 **8 个**控制点（`L` 为连线长度，`H` 为净空高度，`p` 为平顶位置比例，
`top` 为平顶长度）：

| 序号 | u 坐标 | v（高度） | 作用 |
| --- | --- | --- | --- |
| 1 | `0` | `0` | 第一焊点（C1） |
| 2 | `lead`（进出线距离，默认 10 µm） | `rise·H` | 出线点，模拟劈刀抬起 |
| 3 | `p·L − top/2` | `H` | **平顶起点** |
| 4 | `p·L` | `H` | **平顶中点** |
| 5 | `p·L + top/2` | `H` | **平顶终点** |
| 6 | 5 与 7 的中点 | 落在 5→7 直线上 | 下降段中点（**与两端共线**） |
| 7 | `L − lead`（进出线距离） | `fall·H` | 落线点 |
| 8 | `L` | `0` | 第二焊点（C2） |

控制点经 `Part.BSplineCurve.interpolate()` 插值成**穿过所有控制点**的平滑样条；随后映射回三维：`P(u, v) = C1 + u·x + v·y`。

> 形状系数集中在 `core.py` 顶部的 `RISE_POSITION` / `MID_RISE_POSITION` / `DESCENT_POSITION` /
> `FALL_POSITION` 等常量中，便于与参数文档、绘图脚本保持同步。
>
> **为什么是 7 个点**：早期用 8 个点、落线点取 `p·L + 0.92·tail`，末段过短过陡，
> 插值样条会越过 C2 折回（实测 `p = 0.80` 时过冲 0.024 mm）。把落线点前移到
> `0.78·tail` 后末段坡度由 1.56–6.25 降到 0.57–2.27，**过冲完全消除**；
> 代价是落线不再垂直（`p = 0.42` 时约 +48°），可用「落线高度比例」调节。

**不变量**：

- 曲线两个端点严格等于 `C1` 与 `C2`（实测误差 < 1e-7 mm）；
- 曲线 `y` 方向坐标恒为 0，即严格落在平分平面内；
- 曲线完全由 `H`、`p`、`rise`、`fall` 控制，与朝向无关。

### 4.3 FR-4 的金线实体（放样）

```
1. 取路径起点 P0 与该点切向 t = normalize(tangentAt(FirstParameter))
2. 截面 = makeCircle(R, P0, t)     # 垂直于路径切线的圆, 半径 R = 直径/2
3. 实体 = path.makePipeShell([截面], makeSolid=True, isFrenet=False)
4. 若体积为负 (壳体法向朝内) -> shape.copy().reverse() 修正
```

**验证指标**：实体体积应等于 `π·R²·L_curve`。实测 20 µm 直径、曲线长 103.233 mm 时：

| 量 | 数值 |
| --- | --- |
| 实测体积 | `324.3232 mm³`（2 mm 直径标定用例） |
| 理论体积 `π·r²·L` | `324.32 mm³` |

### 4.4 FR-7 焊球

两个焊球为球体，圆心位于两个面的质心，半径 `BallDiameter / 2`。实测体积与 `4/3·π·r³` 完全一致（`0.0005235988 mm³`，r = 50 µm）。

---

## 5. 非功能需求

| 类别 | 要求 | 实现要点 |
| --- | --- | --- |
| 兼容性 | FreeCAD 1.0 / 1.1；PySide2 与 PySide6 均可 | 枚举转换做 `.value` 回退；`set_box_aspect` 类调用做能力判断 |
| 启动安全 | 插件加载失败**不得**影响 FreeCAD 启动 | `InitGui.py` 用兜底 `try/except` 包裹；异常写入日志 |
| 可诊断性 | 加载异常必须可定位 | 每次加载写 `wirebonder_load.log`（插件目录 + `%TEMP%`） |
| 性能 | 常用操作应当即时 | 默认只生成中心线；放样（细直径）耗时较长时由用户显式勾选 |
| 可维护性 | 几何逻辑不依赖 GUI，可单测 | `core.py` 只依赖 `FreeCAD`/`Part` |
| 易用性 | 默认值贴合工艺、面板说明清晰 | 直径 20 µm、净空 500 µm、焊球 50 µm；面板含灰色提示文字与橙色作用域提示 |
| 无额外依赖 | 不引入 pip 依赖 | 仅使用随 FreeCAD 分发的模块 |
| 国际化 | 界面文字跟随 FreeCAD 语言；中文显示中文，其余语言回退英文 | `WireBonder/i18n.py`：三级语言探测 + 字典翻译，无 Qt Linguist 依赖 |

**性能数据（实机）**：

| 操作 | 耗时 |
| --- | --- |
| 中心线生成（参数化重建） | 瞬间 |
| 20 µm 直径 × 约 100 mm 路径放样 | 约 1 分钟（OCCT 在小半径长路径下需要很小容差） |
| 2 mm 直径同名路径放样 | 数秒 |

---

## 6. 架构设计

### 6.1 模块分层

```
                     ┌─────────────────────────────┐
   加载层            │ Init.py        (非 GUI 入口) │
                     │ InitGui.py     (工作台注册)  │
                     └──────────────┬──────────────┘
                                    │ import
                     ┌──────────────▼──────────────┐
   交互层            │ commands.py   (命令/选择校验)│
                     │ taskpanel.py  (参数面板)     │
                     └──────────────┬──────────────┘
                                    │
                     ┌──────────────▼──────────────┐
   模型层            │ features.py                  │
                     │  WireBondFeature             │
                     │  BisectorPlaneFeature        │
                     │  (+ ViewProvider 显示样式)   │
                     └──────────────┬──────────────┘
                                    │
                     ┌──────────────▼──────────────┐
   几何核心          │ core.py  (纯 Part 运算)      │
                     └─────────────────────────────┘
```

### 6.2 目录结构

```
src/                                  # 插件源码 (安装时复制为 <Mod>/WireBonder)
├── Init.py                           # 非 GUI 入口; 同时是"插件目录"的标记
├── InitGui.py                        # 工作台注册 (单函数结构)
├── package.xml                       # Addon Manager 元数据
├── README.md                         # 插件使用/排错说明
└── WireBonder/                       # Python 包
    ├── __init__.py                   # 版本与简介
    ├── i18n.py                       # 多语言 (中/英, 跟随 FreeCAD 语言)
    ├── core.py                       # 几何核心 (无 GUI 依赖)
    ├── features.py                   # 参数化对象 + ViewProvider
    ├── taskpanel.py                  # 参数输入面板
    ├── commands.py                   # FreeCAD 命令
    └── resources/icons/              # WireBonder.svg / WireBond_Create.svg / WireBond_Plane.svg
```

### 6.3 核心 API

```python
# core.py
face_from_subname(shape, "Face3") -> Part.Face
face_centre_and_normal(face)      -> (Vector centre, Vector normal)
make_frame(c1, n1, c2, n2)        -> Frame(origin, xdir, ydir, zdir, length)
loop_profile(L, H, peak_ratio, rise_ratio, fall_ratio) -> [(u, v), ...]
to_world(frame, points2d)         -> [Vector, ...]
build_centreline(points3d)        -> Part.Wire        # 插值样条
sweep_wire(path_wire, diameter)   -> Part.Solid       # 圆截面放样 + 法向修正
bond_balls(c1, c2, diameter)      -> [Part.Solid, ...]
plane_face(frame, margin, width_factor) -> Part.Face  # 辅助面矩形
compute_from_faces(face1, face2, **params) -> dict    # 一步式入口
```

```python
# features.py
WireBondFeature(obj)          # 参数化金线: execute() 内重建 Shape
BisectorPlaneFeature(obj)     # 参数化辅助面
ViewProviderWireBond(vobj)    # 金色显示样式
ViewProviderBisectorPlane(vobj)  # 半透明绿色显示样式
```

---

## 7. 数据模型

### 7.1 `WireBond`（Part::FeaturePython）

| 属性 | 类型 | 默认 | 单位 | 说明 |
| --- | --- | --- | --- | --- |
| `Face1` | `App::PropertyLinkSub` | — | — | 第一个面 |
| `Face2` | `App::PropertyLinkSub` | — | — | 第二个面 |
| `WireDiameter` | `App::PropertyLength` | 0.02 | mm | 金线直径（20 µm） |
| `Clearance` | `App::PropertyLength` | 0.5 | mm | 净空高度（弧顶相对连线），即 **500 µm** |
| `PeakRatio` | `App::PropertyFloat` | 0.42 | — | 拱顶位置占连线长度比例（0.05–0.95） |
| `RiseRatio` | `App::PropertyFloat` | 0.60 | — | 出线陡升点高度比例（0–1） |
| `FallRatio` | `App::PropertyFloat` | 0.20 | — | 落线高度比例（0–0.6） |
| `MakeSolid` | `App::PropertyBool` | False | — | 是否生成金线实体 |
| `ShowCentreline` | `App::PropertyBool` | True | — | 是否同时显示中心线 |
| `MakeBalls` | `App::PropertyBool` | True | — | 是否生成焊球 |
| `BallMode` | `App::PropertyEnumeration` | `sphere` | — | 凸起形状（旧属性，两端相同时有效）：`none` / `sphere` / `frustum` |
| `StartBallMode` | `App::PropertyEnumeration` | `sphere` | — | C1 处的凸起形状 |
| `EndBallMode` | `App::PropertyEnumeration` | `sphere` | — | C2 处的凸起形状 |
| `LeadDistance` | `App::PropertyLength` | 0.01 | mm | 焊盘到进出线控制点的水平距离（**10 µm**） |
| `TopLength` | `App::PropertyLength` | 0.20 | mm | 平顶平直段长度（**200 µm**） |
| `BallDiameter` | `App::PropertyLength` | 0.05 | mm | 球径（球形）或凸点高度（圆台） |
| `BallTopDiameter` | `App::PropertyLength` | 0.05 | mm | 圆台远离焊盘一端的直径 |
| `BallBottomDiameter` | `App::PropertyLength` | 0.05 | mm | 圆台贴着焊盘一端的直径 |
| `PlaneRotation` | `App::PropertyAngle` | 0° | — | 走线平面绕两质心连线的偏转角（0° = 与原平分平面重合） |

`Shape` 的构成取决于参数：

| 条件 | Shape |
| --- | --- |
| `MakeSolid=False`（默认） | 中心线 `Wire`（若 `MakeBalls=True` 则为含球体的 `Compound`） |
| `MakeSolid=True` | `Compound([Solid, (中心线), (焊球…)])` |

### 7.2 `WireBondPlane`（Part::FeaturePython）

| 属性 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `Face1` / `Face2` | `App::PropertyLinkSub` | — | 与金线相同的两个面 |
| `Margin` | `App::PropertyLength` | 2.0 mm | 矩形沿连线两端的外扩量 |
| `WidthFactor` | `App::PropertyFloat` | 0.35 | 矩形半宽 = 连线长度 × 该系数 |
| `PlaneRotation` | `App::PropertyAngle` | 0° | 走线平面绕两质心连线的偏转角（与金线保持一致） |

> 该对象由 `Create Wire Bond` 创建时**自动隐藏**（`ViewObject.Visibility = False`），属于辅助几何；`Create Bisector Plane` 命令创建的辅助面保持显示，便于单独查看。

---

## 8. 交互设计

### 8.1 主流程

```
用户                         插件
 │  选中两个面 (Ctrl 多选)
 │ ─────────────────────────► │  校验: 恰好两个面? 是平面? 法线可算?
 │                            │  预检: 法线是否反平行? 连线是否与平分线平行?
 │                            │  (失败 -> 弹窗说明原因并中止)
 │ ◄───────────────────────── │  打开参数面板 (显示两面质心/法线)
 │  调整参数 (直径/净空/焊球…)
 │  点击 OK
 │ ─────────────────────────► │  openTransaction
 │                            │  创建 WireBond (+ WireBondPlane 并隐藏)
 │                            │  recompute / commitTransaction
 │ ◄───────────────────────── │  自动切换等轴测视图, 完成
```

### 8.2 面板字段

| 字段 | 控件 | 默认 | 备注 |
| --- | --- | --- | --- |
| 选中的平面 | 只读文本 | — | 显示 `对象: FaceN`、质心与法线，便于确认选择正确 |
| 金线直径 | 数值输入（µm） | 20 | 0.1–500 µm |
| 净空高度 | 数值输入（µm） | 500 | 0–100000 µm（内部按 mm 存储） |
| 走线平面偏转角 | 数值输入（°） | 0 | −180°–180°，步进 5°；0° 与原平分平面重合 |
| 拱顶位置比例 | 数值输入 | 0.42 | 0.05–0.95 |
| 出线陡升比例 | 数值输入 | 0.60 | 0–1 |
| 落线高度比例 | 数值输入 | 0.20 | 0–0.6 |
| 焊球直径 | 数值输入（µm） | 50 | 1–20000 µm |
| 生成金线实体 | 复选 | 否 | 勾选后生成真实直径实体（较慢） |
| 同时显示中心线 | 复选 | 是 | 细直径下便于看清走线 |
| 生成焊球 | 复选 | 是 | 与“焊球直径”联动 |
| 创建平分辅助面 | 复选 | 否 | 生成后自动隐藏；默认不创建以减少对象数量 |

### 8.3 错误与提示

| 场景 | 提示方式 |
| --- | --- |
| 未选够两个面 / 选中了边或点 | 命令灰显；执行时弹窗说明当前识别到的面数 |
| 两个面法线反平行 | 弹窗：“两个平面的法线互成 180 度，平分线不存在；请选择朝向一致的两个面。” |
| 连线与平分线平行 | 弹窗：“质心连线方向与法线平分线平行，无法唯一确定平面……” |
| 生成过程异常 | 弹窗显示异常信息，事务回滚，不留下半成品对象 |

---

## 9. 关键实现约束（踩坑记录）

这一节是**必须遵守的实现约束**，否则插件会"静默失效"。

### 9.1 FreeCAD 的插件加载方式

FreeCAD 以 `exec(code, globals, locals)` 执行 `InitGui.py`，且 **`globals` 与 `locals` 不是同一个字典**，由此产生两个陷阱：

| 陷阱 | 后果 | 规避方式 |
| --- | --- | --- |
| 命名空间里**没有 `__file__`** | 用 `__file__` 定位图标目录会 `NameError` | 通过已导入包的 `WireBonder.__file__` 定位；`__file__` 仅作兜底分支 |
| **顶层函数引用模块级变量会 `NameError`** | 模块级赋值只写进 `locals`，函数查名字用 `globals` | **全部逻辑写在单个函数内部**，只用局部/闭包变量 |

实测报错（原始日志）：

```
File "...\Mod\WireBonder\.\InitGui.py", line 127, in <module>
    _log("---- loading WireBonder addon ----")
  File "...\InitGui.py", line 61, in _log
    _LOG_LINES.append(...)
NameError: name '_LOG_LINES' is not defined
```

### 9.2 插件目录必须同时含 `Init.py`

FreeCAD 遍历 Mod 下的每个子目录时，**只有存在 `Init.py` 才视为插件**，否则启动日志打印：

```
Initializing ...\Mod\WireBonder(Init.py not found)... ignore
```

因此 `src/Init.py` 不只是"非 GUI 入口"，它同时是**插件目录的标记文件**。

### 9.3 PySide6 枚举差异

Qt6 的枚举是 `enum.Flag`，`int(QDialogButtonBox.Ok | Cancel)` 会抛
`TypeError: int() argument must be a string, ... not 'StandardButton'`；
必须回退到 `.value`。代码：

```python
buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
try:
    return int(buttons)          # PySide2
except TypeError:
    return int(buttons.value)    # PySide6
```

### 9.4 `Part.Shape` 的只读性

`obj.Shape.reverse()` 会抛
`ReferenceError: This object is immutable, you can not set any attribute or call a non const method`；
正确做法是先复制再修改：

```python
shape = obj.Shape.copy()
shape.reverse()
obj.Shape = shape
```

### 9.5 `Body` 作用域提示

当所选面位于 `PartDesign::Body` 内部时，创建外部对象会产生警告：

```
Wrn: Part::FeaturePython: Link(s) to object(s) 'Pad002' go out of the allowed scope 'WireBond'.
```

这是**警告而非错误**，几何结果正确；如需彻底避免，可把焊盘做成独立 Part 对象，或将生成对象放入与 Body 同级的 `App::Part`。

### 9.6 父容器变换（装配体坐标系）

`obj.Shape` **只包含对象自身**的 Placement，**不含父容器**（`App::Part` / `PartDesign::Body`）的 Placement：

```python
face.CenterOfMass          # 局部坐标: 少了一层父级变换
obj.getGlobalPlacement()   # 父链 + 自身的复合变换
extra = obj.getGlobalPlacement() * obj.Placement⁻¹   # 父链贡献的变换
face_global = face.transformed(extra.toMatrix())
```

位于装配体（`App::Part`）内的零件必须做上述补偿，否则金线会画到模型之外。实测数据：

| 对象 | 自身 Placement | getGlobalPlacement | 面质心（局部 → 全局） |
| --- | --- | --- | --- |
| `09_L2049D007`（父 `_09_L2049D0`） | Pos=(0, 0, 0.121) | Pos=(7.335, -0.802, 0.231) | (1.304, 0.076, 0.131) → **(8.639, -0.726, 0.362)** |
| `PD_Sub mount`（父为根级 Part） | Pos=(8.285, 0.148, -0.390) | 同左（父级为恒等） | (8.865, -0.432, 0.111) → 同值 |

未补偿时两端的坐标系不一致：一端恰好正确、另一端偏移约 7.3 mm —— 现象就是“金线起点跑到装配体之外”。
几何核心 `core.global_face(obj, subname)` 统一负责该变换，`features` 与 `commands` 均通过它取面。

---

## 10. 测试与验证

### 10.1 已完成的验证

| # | 用例 | 方法 | 结果 |
| --- | --- | --- | --- |
| T-1 | 平分平面构造 | 两个水平焊盘顶面 | 平面法向 `(0, -1, 0)`，即竖直平分面，与手工模型一致 |
| T-2 | 曲线端点 | 比较曲线首尾点与质心 | 误差 `< 1e-7 mm` |
| T-3 | 曲线共面性 | 检查曲线包围盒 `y` | `y` 恒为 0，严格在平分平面内 |
| T-4 | 参数化联动 | `Clearance` 2 mm → 5 mm | 包围盒 `ZMax` 由 20.051 → 21.175 mm 自动更新 |
| T-5 | 金线实体体积 | 直径 2 mm 标定件 | 324.3232 vs 理论 324.32 mm³ |
| T-6 | 焊球体积 | 直径 100 µm | `0.0005235988 mm³`，与 `4/3πr³` 一致 |
| T-7 | 焊球位置 | 球心坐标 | 精确落在两个面质心 |
| T-8 | 关闭焊球 | `MakeBalls=False` | 实体数 2 → 0 |
| T-9 | 命令注册 | `Gui.listCommands()` | `['WireBonder_CreatePlane', 'WireBonder_CreateWireBond']` |
| T-10 | 工作台注册 | `Gui.listWorkbenches()` | `WireBonderWorkbench` 存在，图标路径有效 |
| T-11 | 真实启动加载 | `FreeCAD.exe --log-file` | `Initializing ...\WireBonder\.\... done` + `addWorkbench OK` |
| T-12 | 面板按钮 | 构造面板并取按钮 | 返回 int `4195328`，无异常 |
| T-13 | 面板默认值 | 读取控件值 | 净空 500 µm、焊球 50 µm、辅助面不勾选、可正确取到面板按钮 |
| T-14 | 装配体坐标系 | `09_L2049D007.Face1` + `PD_Sub mount.Face103` | 质心由局部 (1.304, 0.076, 0.131) 修正为全局 (8.639, -0.726, 0.362)，生成曲线起点与全局质心一致（< 1e-6 mm） |
| T-15 | 间距提醒 | L=0.393 mm、净空 500 µm | 面板显示“净空高度大于两质心间距”的橙色提示 |

### 10.2 建议的补充测试（待办）

- 两个倾斜平面（法线夹角 30°/90°）的平分平面正确性；
- 退化输入（重合质心、法线反平行）的提示行为；
- 大尺寸/微小尺寸（µm 级焊盘）下的数值稳定性；
- 在 FreeCAD 1.0 与 Qt5 环境（PySide2）下的回归。

---

## 11. 安装与部署

| 项目 | 说明 |
| --- | --- |
| 安装方式 | 把 `src` 目录复制为 `<Mod>/WireBonder`（`xcopy /E /I /Y src "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"`） |
| 生效方式 | 重启 FreeCAD（插件在启动时加载） |
| 验证 | 工作台下拉出现 **Wire Bonding**；或查看 `wirebonder_load.log` 是否以 `addWorkbench OK` 结尾 |
| 升级 | 覆盖目录后重启；必要时先删除安装目录中的 `__pycache__` |
| 卸载 | 删除 `<Mod>/WireBonder` 目录并重启 |

完整的安装/排错步骤见 [`README.md`](../README.md)。

---

## 12. 已知限制

| 限制 | 说明 | 可能的改进方向 |
| --- | --- | --- |
| 细直径放样慢 | 20 µm × 100 mm 约 1 分钟 | 减小路径采样、调整放样容差；或后台线程中生成 |
| 净空高度定义 | 为"弧顶相对两质心连线的高度"，不是相对元器件表面 | 增加"以指定基准面/平面为参考"的选项 |
| 落线角度偏斜 | 为保证不过冲，落线点前移到 `0.78·tail`，末段变长变缓，到达 C2 时不再垂直（`PeakRatio = 0.42` 约 +48°）；`PeakRatio = 0.20/0.42/0.60/0.80` 分别约 +57°/+48°/+38°/+25° | 把落线点位置也做成参数（如 `FallPositionRatio`），让用户在"垂直落线"与"无过冲"之间权衡 |
| 单根金线 | 一次只生成一根 | 支持多面选择批量生成、或阵列（Array）参数化 |
| 弧线形状 | 单一 loop profile | 增加 BS / BSS / SSB 等工艺预置 profile |
| 实体与中心线同色 | `Compound` 内只能一种颜色 | 拆成独立对象或使用 ViewProvider 自定义绘制 |
| `Body` 作用域警告 | 选中 Body 内面时出现（已加中文提示，属警告非错误） | 把焊盘改用 Part 工作台建模可彻底避免 |
| PartDesign 阵列不可变换 | 对 `LinearPattern` 使用变换工具会报 `Only additive and subtractive features can be transformed`（与插件无关） | 改阵列参数，或选中 `Body` 移动其 `Placement` |

---

## 13. 后续规划

| 版本 | 计划 |
| --- | --- |
| v0.2 | 多段/多根金线批量生成；loop profile 预置（BS/BSS/SSB）；`Clearance` 支持以基准面为参考 |
| v0.3 | 后台线程生成实体并显示进度条；导出金线为独立 STEP/STL |
| v0.4 | 与 FEM 工作台联动：一键把金线加入分析（材料=金、线径=实测）；线弧长度/电阻估算 |
| v0.5 | 打线布局校验：净空干涉检查、最小间距检查、导出坐标表给打线机 |

---

## 14. 面板参数持久化

| 项目 | 说明 |
| --- | --- |
| 存储位置 | `User parameter:BaseApp/Preferences/Mod/WireBonder`（FreeCAD 用户参数，**不写入 .FCStd**） |
| 触发时机 | 面板点 **OK** 成功后写入；面板构造时读取并回填 |
| 持久化字段 | `WireDiameter` / `Clearance` / `BallDiameter` / `PlaneRotation` / `PeakRatio` / `RiseRatio` / `FallRatio` / `MakeSolid` / `ShowCentreline` / `MakeBalls` / `CreatePlane`（长度以 mm 存储，面板负责 µm 换算） |
| 读取兜底 | 逐项独立读取，缺失或类型异常时回退到 `core` 中的内置默认值；`Settings.load_checked()` 还会把值夹到面板控件的合法区间，防止手工改坏参数后界面出现异常值 |
| 重置方式 | 面板底部 **恢复默认值** 按钮（同时清空存储），或 `Tools ▸ Edit parameters ▸ BaseApp ▸ Preferences ▸ Mod ▸ WireBonder` |
| 注意事项 | `ParamGet` 按类型分别存储，删除必须用对应方法（数值 `RemFloat`、布尔 `RemBool`）；用 `RemString` 删数值会静默失败 |

> 持久化的只是**面板默认值**。已创建的对象保留自身属性，改默认值不会追溯修改既有几何。

## 15. 国际化设计

### 14.1 语言判定

| 顺序 | 来源 | 说明 |
| --- | --- | --- |
| 1 | `FreeCADGui.getLocale()` | GUI 环境首选，返回如 `'Chinese (Simplified)'` |
| 2 | `User parameter:BaseApp/Preferences/General` → `Language` | 无 GUI 也可用 |
| 3 | `PySide.QtCore.QLocale.system().name()` | 如 `zh_CN` |
| 4 | 兜底 | 英文 |

归一化规则：以 `zh` 开头或含 `chinese` → **中文**；其余一律 **英文**。结果由 `i18n.language()` 缓存，可用 `i18n.set_language(code)` 覆盖（测试用），传 `None` 恢复自动探测。

### 14.2 词条组织

* **英文原文即 msgid**，源码中写 `_("Wire Diameter")`；
* 中文词条表 `_ZH` 为核心数据结构，未命中的 key 原样返回，因此**永不出现空白或 key 泄漏**；
* 带占位符的句子同样以英文为 msgid，由调用方 `.format()`，例如
  `_("Centroid distance L = {:.3f} mm").format(length)`。

### 14.3 覆盖范围

| 模块 | 本地化内容 |
| --- | --- |
| `InitGui.py` | 工作台名称、ToolTip、工具栏/菜单分组名 |
| `commands.py` | 菜单项、ToolTip、选择校验弹窗、Console 输出、错误对话框 |
| `taskpanel.py` | 面板标题、分组名、全部字段标签、复选框、提示与警告文字 |
| `features.py` | 全部属性描述（属性编辑器中显示） |
| `core.py` | 全部异常消息与警告（`_normalize()` 的 `what` 参数也走翻译） |

### 14.4 已知取舍

* 不生成 `.ts`/`.qm`，避免引入 Qt Linguist 工具链；插件规模小，字典方式更易维护。
* 语言在**加载时确定**（`language()` 带缓存），运行中修改 FreeCAD 语言需重启 FreeCAD 才能切换界面。
* 英文词条没有独立表，直接复用 msgid，因此英文文案以源码中的写法为准。

## 16. 文档配图工具

参数文档 [`parameters.md`](parameters.md) 的示意图由 `scripts/` 下的独立脚本生成，**不依赖 FreeCAD**：

| 脚本 | 输出 | 说明 |
| --- | --- | --- |
| [`scripts/plot_peak_ratio.py`](../scripts/plot_peak_ratio.py) | `docs/images/peak-ratio.png` | 四个 `PeakRatio` 取值下的弧线形态对比：复用与 `core.loop_profile()` 完全相同的控制点公式，再用弦长参数化的三次样条平滑，模拟 `Part.BSplineCurve.interpolate()` 的行为 |

实现要点：

- 仅依赖 **matplotlib + numpy**（自然三次样条用 Thomas 算法自行实现，避免引入 SciPy）；
- 字体自动挑选可用中文字体（Microsoft YaHei / SimHei / Noto Sans CJK …），缺失时回退；
- **必须使用参数化样条**：若把 `v` 当作 `u` 的函数插值，样条会在控制点之间明显过冲（实测最高 5%），
  会错误地暗示线弧高于净空高度；参数化后过冲降至 3.5% 以内，与 FreeCAD 中的实际几何一致；
- 脚本同时把表格所需数值打印到标准输出，便于核对文档中的数据。

## 17. 附录

### 14.1 关键 FreeCAD API

| API | 用途 |
| --- | --- |
| `Face.CenterOfMass` | 面质心 |
| `Face.normalAt(0.5, 0.5)` | 面法线（按面朝向） |
| `Part.BSplineCurve().interpolate(points)` | 穿过控制点的插值样条 |
| `Part.makeCircle(r, center, normal)` | 放样截面 |
| `Wire.makePipeShell([profile], makeSolid, isFrenet)` | 沿路径扫掠 |
| `Part.makeSphere(r, center)` | 焊球 |
| `doc.addObject("Part::FeaturePython", name)` + `obj.Proxy.execute()` | 参数化对象 |
| `Gui.Control.showDialog(panel)` / `panel.getStandardButtons()` | 任务面板 |
| `Gui.Selection.getSelectionEx()` → `SubElementNames` | 获取用户选中的面 |

### 14.2 修订记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v0.1.0 | 2026-09-21 | 首个版本：平分平面 + 打线弧 + 金线实体 + 焊球 + 参数化对象；辅助面自动隐藏；修复 `InitGui.py` 加载陷阱与 PySide6 枚举兼容问题 |
| v0.1.1 | 2026-09-21 | 净空高度默认改为 **500 µm**（面板输入单位改为 µm）、焊球直径默认 **50 µm**；平分辅助面改为**默认不创建**；新增 `PartDesign::Body` 作用域提示（面板橙色提示 + Report view 中文说明） |
| v0.1.2 | 2026-09-21 | **修复装配体坐标系 bug**：新增 `core.global_face()`，补偿 `App::Part` 等父容器变换（此前质心按局部坐标计算，金线画到模型之外）；面板质心显示改为全局坐标，并显示两质心间距 L 与“净空高度大于间距”提醒 |
| v0.1.3 | 2026-09-21 | 新增**走线平面偏转角** `PlaneRotation`（`App::PropertyAngle`，默认 `0°`）：`core.make_frame()` 支持把 y/z 轴绕质心连线旋转，金线所在的平面随之偏转；金线与辅助面同参数联动 |
| v0.2.0 | 2026-09-22 | 新增**多语言支持**（`WireBonder/i18n.py`）：跟随 FreeCAD 语言设置，中文显示中文、其它语言回退英文；`InitGui` / `commands` / `taskpanel` / `features` / `core` 的用户可见文案全部走 `_()`；启动日志新增 `language = zh/en` 记录 |
| v0.3.0 | 2026-09-22 | **切换语言无需重启**（`WireBonder/language_monitor.py`）：同时监视 `Language` 用户参数与 `FreeCADGui.getLocale()`，变化即刷新 i18n 缓存、调用 `setLocale()` 同步 GUI、重新注册工作台，并用 `QTimer.singleShot(0, ...)` 延后重设 QAction 文字（FreeCAD 处理 `LanguageChange` 时会覆盖） |
| v0.4.0 | 2026-09-22 | 新增**面板参数持久化**（`WireBonder/settings.py`）：OK 后把 11 项参数写入 `User parameter:BaseApp/Preferences/Mod/WireBonder`，下次打开面板自动回填；新增「恢复默认值」按钮；注意 `ParamGet` 数值/布尔需分别用 `RemFloat` / `RemBool` 删除 |
| v0.5.0 | 2026-09-22 | **面板可滚动 + 分组可折叠**：外层套 `QScrollArea`（`setWidgetResizable(True)`，禁用横向滚动条）；新增 `CollapsibleBox` 取代 `QGroupBox`（`QGroupBox` 的 checkable 只能禁用内容、无法隐藏）；折叠状态持久化为 `ui_show_*` 并与几何参数分开保存。规避两个 Qt 陷阱：自动换行 `QLabel` 的 `minimumSizeHint` 等于最长单词宽度会撑宽面板，需 `setMinimumWidth(1)`；`setChecked()` 发出的 `toggled` 信号会与程序化状态更新互相递归，需 `blockSignals` 隔离 |
| v0.6.0 | 2026-09-22 | **打线弧控制点由 8 个减为 7 个**（弧顶居中、左右各 3 个）：取消原第 6 个下降点，落线点由 `0.92·tail` 前移至 `0.78·tail`，末段坡度从 1.56–6.25 降到 0.57–2.27，**越过 C2 的过冲完全消除**（原 8 点方案在 `PeakRatio = 0.60/0.80` 时分别为 0.00575/0.02416 mm）。形状系数抽为 `RISE_POSITION` / `MID_RISE_POSITION` / `DESCENT_POSITION` / `FALL_POSITION` 等模块常量，并与 `scripts/plot_peak_ratio.py`、参数文档保持一致。代价：落线不再垂直（`PeakRatio = 0.42` 约 +48°），可用「落线高度比例」调节 |
| v0.7.0 | 2026-09-22 | **数值输入改用 `Gui::QuantitySpinBox`**（与属性视图同款控件）：① **自由切换单位** —— 单位随值存储，可直接输入 `20 um` / `0.02 mm` / `1 thou`，长度与角度各用对应的量纲；② **表达式求值** —— `10*2`、`5um*4`、`Spreadsheet` 引用均可；③ **滚轮不再误改数值** —— `_WheelGuard` 事件过滤器拦截 `QEvent.Wheel` 并转交给面板的滚动区。三个实现要点：`installEventFilter()` 不接管对象所有权，过滤器必须挂到控件上作子对象否则会被 GC；必须用 `App.Units`（模块把 FreeCAD 别名为 `App`，写成 `FreeCAD.Units` 会抛 `NameError` 并被兜底静默吞掉，导致单位丢失、`0.001 in` 被当成 0.001 mm）；`setProperty("value", ...)` 之后**不能**调用 `interpretText()`，它会用滞后的输入框文本覆盖新值 |
| v0.8.0 | 2026-09-22 | **焊点凸起改为三态可选**（新增 `core.bond_bumps()`）：`none` / `sphere` / `frustum`。球形沿用 `Part.makeSphere`；圆台用 `Part.makeCone(bottom_r, top_r, height, centre, axis, 360)` 生成截锥，并**沿该焊盘的外法线定向**（实测法线 +Z 时 `z[0, 0.05]`、−Z 时 `z[-0.05, 0]`）。体积校验：球 φ50 µm = `0.000065450 mm³`、圆台 φ80→φ30 × 高 50 µm = `0.000126973 mm³`，与解析式完全一致。面板新增「焊球形状」下拉框并**按选择动态显隐**直径字段（无→全隐藏；球形→仅球径；圆台→上下底直径）；原「生成焊球」复选框保留为快捷开关，与下拉框双向联动（取消→无、重勾→恢复上次形状）。`settings.py` 新增字符串类型持久化以保存 `BallMode`。踩坑：`PropertyEnumeration` 必须**先赋选项列表再赋当前值**，且读取选项要用 `getEnumerationsOfProperty()`——`list(obj.BallMode)` 会迭代当前值字符串，产生 `['s','p','h','e','r','e']` 的假象 |
| v0.9.0 | 2026-09-22 | **两端形状独立 + 进出线距离**。① `core.bond_bumps` 的两端可分别指定形状（`start_ball_mode` / `end_ball_mode`），新增 `StartBallMode` / `EndBallMode` 两个枚举属性与面板上的两个下拉框；共用的直径字段按两端合并显示（任一端为球形则显示球径、任一端为圆台则显示上下底）。② 新增 `LeadDistance`（默认 **10 µm**），用**绝对距离**定位第 2、第 6 控制点（`p2.u = lead`、`p6.u = L − lead`），使进出线角度只由高度比例与该距离决定、与连线长度解耦；实测 lead 2/10/50 µm 对应出线斜率 150/30/6，出线角 −23.4°/−21.9°/−14.5°。③ 该距离自动夹紧到 `peak_u`/`tail` 的 45% 以内，保证 7 个控制点顺序合法（实测 lead=10 mm + peak_ratio=0.10 时夹到 0.09 mm）。踩坑：`_last_ball_modes` 是 `(start, end)` 元组，恢复时必须逐端解包，否则复选框重勾后两端都停在 `none` |
| v0.9.1 | 2026-09-22 | **修正面板字段标签**。① 字段标签不再使用可收缩的 `_wrap_label()`（它是给长注释用的，会把标签列压到一行一个字），改用普通 `QLabel`；实测标签恢复为 58×31 px 单行；② 标签精简为「上底直径」「下底直径」（原「圆台上底直径」过长）。这是 v0.9.0 引入两个下拉框后暴露的显示问题 |
| v0.10.0 | 2026-09-22 | **线形改为真实打线轮廓（平顶 + 长直下降）**，依据 `data/wire-sketch.png` 与 `data/sketch-params.png`。控制点由 7 个改为 **8 个**：平顶由 **3 个点**支撑（此前 2 点，样条在过渡处上拱，实测最高点超出设定净空 **6.8%**，3 点后降到 **1.8%**，使「净空高度」参数可信）；下降段中间点**与两端共线**，利用三点共线使自然样条二阶导数为零的性质让下降段成为**真正的直线**（实测偏离直线 RMS 约 3 um）。新增参数 `TopLength`（平顶长度，默认 **200 µm**，贴近参考图的 `0.3·L`，自动夹紧到跨度的 45%）；`FallRatio` 默认由 0.20 改为 **0.12** 以进一步压平下降段。新增两个对照/扫描脚本：`scripts/compare_profile.py`（按参考图比例出图并打印平顶跨度、下降斜率、偏离直线比例）与 `scripts/scan_top_length.py`（平顶长度 x 跨度网格扫描） |
| v0.10.1 | 2026-09-22 | **修复两个缺陷并改善报错可诊断性**。① 平顶平台未受峰值位置约束：`u3 = peak_u − top/2` 在 `peak_ratio` 较小（如 0.05）或较大（0.90）时会落到 C1 之前/落线点之后，使 8 个控制点的 u 不再递增（实测 1680 组参数中有 421 组非法，最坏情况出现 `u3 = 0` 甚至负值）。改为**双侧夹紧**：`half_top = min(top/2, 0.45L/2, min(peak_u − lead, (L − lead) − peak_u) × 0.98)`，取两侧可用空间较小者并留 2% 余量；复测 **1680 组全部合法**。② `_restore_defaults()` 中 `LeadDistance` 被重复设置了一行（插入新字段时的冗余），已清理。③ `accept()` 的异常分支现在把完整调用栈写入 Report view（此前只弹一句异常文字，难以定位）；报错文案相应更新 |

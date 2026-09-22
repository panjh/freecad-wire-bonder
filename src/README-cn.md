# WireBonder — FreeCAD 打线（金线）辅助插件

选中任意**两个平面**，插件会构造一个“平分平面”，并在该平面内画出一条连接两个质心的**打线弧（wire loop）**，最后按设定的**金线直径**把它放样成实体（可选生成两个焊球）。

金线直径、净空高度、拱顶位置等全部是**参数化属性**，改完自动重建几何。

| 相关文档 | 位置 |
| --- | --- |
| **参数详解**（每个参数的作用与调法） | [`../docs/parameters.md`](../docs/parameters.md) |
| 项目设计文档（PRD） | [`../docs/freecad-wirebonder-prd.md`](../docs/freecad-wirebonder-prd.md) |
| 安装操作文档 | [`../README.md`](../README.md) |
| 插件源码 | 本目录 [`src/`](.) |

> 版本 0.2.0 ｜ 已在 **FreeCAD 1.1.3 + Python 3.11.14 + PySide6 6.8.3** 上实测通过。
>
> **v0.2.0 变更**：新增**多语言支持** —— 界面文字随 FreeCAD 的语言设置切换，
> 中文环境显示中文，**其它任何语言（含英文）显示英文**。新增模块 [`WireBonder/i18n.py`](WireBonder/i18n.py)。
>
> **v0.1.3 变更**：新增 **走线平面偏转角** `PlaneRotation`（默认 `0°`，与原平分平面完全重合）——
> 可让金线所在的平面绕两质心连线旋转任意角度。
>
> **v0.1.2 变更（重要修复）**：修正装配体坐标系 —— 面取自 `App::Part` 容器内的零件时，现在会正确补偿
> 父容器的变换（此前质心按局部坐标计算，金线会画到模型之外）。面板质心显示改为**全局坐标**，
> 并新增“两质心间距 L”与“净空高度大于间距”的提醒。
>
> v0.1.1 变更：净空高度默认改为 **500 µm**、焊球直径默认 **50 µm**；平分辅助面改为**默认不创建**；
> 新增 PartDesign Body 作用域提示（面板橙色提示 + Report view 说明）。

---

## 1. 几何构造规则

给定两个被选中的平面 F1、F2：

1. 取两个平面的**质心** C1、C2，得到连线方向 `d = normalize(C2 - C1)`；
2. 取两个平面的**法线** n1、n2，先把它们统一到同一半球（夹角大于 90° 时翻转 n2），再取**角平分方向** `b = normalize(n1 + n2)`；
3. 目标平面 P 由 `d` 与 `b` 张成，它同时通过 C1 与 C2；
4. 在 P 内建立局部坐标系：x 轴沿 `d`，y 轴取 `b` 在 P 内的正交分量（Gram-Schmidt），z 轴为平面法向 `x × y`；
   若设置了**走线平面偏转角** θ（默认 0°），则把 y、z 轴**绕 x 轴（连线）旋转 θ**：即走线平面以连线为轴偏转，0° 时与原平分平面完全重合；
5. 在 P 内生成打线弧：从 C1 出线（陡升）→ 拱顶 → 平缓落回 C2；
6. 用直径为 `WireDiameter` 的圆沿弧线放样，得到金线实体；可选在两个质心处生成球状焊点。

两个典型平面（两个水平焊盘，法线都朝 +Z）会得到**竖直的平分平面**；两个倾斜的焊盘会得到按法线角平分方向倾斜的平面。

### 打线弧控制点

在局部坐标 `(u, v)` 下（`L` = 质心距离，`H` = 净空高度，`p` = 拱顶位置比例）：

| u | v | 含义 |
| --- | --- | --- |
| `0` | `0` | 第一焊点（C1） |
| `0.12·p·L` | `rise·H` | 出线陡升 |
| `0.50·p·L` | `0.92·H` | 上升段 |
| `p·L` | `H` | **弧顶** |
| `p·L + 0.38·tail` | `0.86·H` | 下降段 |
| `p·L + 0.78·tail` | `fall·H` | 落线姿态 |
| `L` | `0` | 第二焊点（C2） |

控制点共 **7 个** —— 弧顶居中，左右各 3 个（`tail = L − p·L`）。

控制点经 `Part.BSplineCurve.interpolate()` 插值成平滑样条，因此曲线**严格穿过两个质心**、并**整体落在平分平面内**（实测端点误差 < 1e-7 mm）。把落线点放在 `0.78·tail` 处，可保证末段足够长，使样条**不会越过第二焊点外鼓**。

## 2. 安装

把项目里的 `src` 目录复制到 FreeCAD 的 Mod 目录，并重命名为 `WireBonder`：

| 平台 | Mod 目录 |
| --- | --- |
| Windows | `%APPDATA%\FreeCAD\v1-1\Mod\` |
| Linux | `~/.local/share/FreeCAD/v1-1/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |

> 目录带版本号（`v1-1` / `v1-0` / `v0.21`），最可靠的做法是在 FreeCAD 控制台执行
> `os.path.join(FreeCAD.getUserAppDataDir(), "Mod")` 查询实际路径。

```bat
:: Windows 示例
xcopy /E /I /Y src "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

```bash
# Linux / macOS
cp -r src ~/.local/share/FreeCAD/v1-1/Mod/WireBonder
```

重启 FreeCAD 后，工作台下拉框中会出现 **Wire Bonding**。

> ⚠ 插件目录**必须同时包含 `Init.py` 与 `InitGui.py`**：FreeCAD 只把含 `Init.py` 的子目录当作插件，
> 否则会在启动日志里打印 `(Init.py not found)... ignore` 并跳过。

也可以在 FreeCAD 里用 Addon Manager 的 “Install from file” 安装 `package.xml` 打包的 zip。

**免重启试用**（当前会话临时加载）：

```python
import os, sys
addon = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder")
if addon not in sys.path:
    sys.path.append(addon)
import WireBonder.commands                      # 注册两个命令
import FreeCADGui as Gui
Gui.activateWorkbench("WireBonderWorkbench")
```

## 3. 使用

1. 在 3D 视图中选中**两个面**（按住 `Ctrl` 多选；可以来自同一个对象，也可以来自两个对象）；
2. 工具栏 **Wire Bonding ▸ Create Wire Bond**（或菜单同名项）；
3. 在弹出的面板中设置参数，点 **OK**；
4. 生成 `WireBond` 对象（金线 + 焊球，金色）；若勾选，还会生成 `WireBondPlane`
   **平分辅助面**（半透明绿色，生成后自动隐藏，需要时可在模型树里手动显示）。

### 面板参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| 金线直径 | 20 µm | 放样截面直径，即金线直径 |
| 净空高度 | 500 µm | 弧顶**相对两质心连线**的高度 |
| 走线平面偏转角 | 0° | 走线平面绕两质心连线的偏转角（−180°~180°）；**0° 与原平分平面完全重合** |
| 拱顶位置比例 | 0.42 | 拱顶位置占连线长度的比例（0.05–0.95） |
| 出线陡升比例 | 0.60 | 起点附近陡升点的高度比例，模拟打线机的出线 |
| 落线高度比例 | 0.20 | 接近终点时的高度比例，控制落线姿态 |
| 焊球直径 | 50 µm | 两个焊点处焊球（bond ball）的直径（约为线径 2.5 倍） |
| 生成金线实体 | 否 | 勾选后生成真实直径的实体；直径很小时放样较慢 |
| 同时显示中心线 | 是 | 只生成中心线时也可显示，便于在小直径下看清走线 |
| 生成焊球 | 是 | 在两个质心处生成焊球，直径由“焊球直径”指定 |
| 创建平分辅助面 | 否 | 额外生成平分平面（构造参考，生成后自动隐藏）；**默认不创建**，可减少对象数量 |

> **面板会记住上次的设置**：点 OK 后当前参数会保存到 FreeCAD 用户参数
> （`User parameter:BaseApp/Preferences/Mod/WireBonder`），下次打开面板时自动回填，
> 包括金线直径、净空高度、走线平面偏转角、各比例、焊球直径与所有复选框。
> 想回到内置默认值，点面板底部的 **恢复默认值** 按钮（同时清除已保存的设置），
> 或在 **Tools ▸ Edit parameters ▸ BaseApp ▸ Preferences ▸ Mod ▸ WireBonder** 中手动删除。

### 面板布局

- **自动滚动**：面板内容超出可用高度时，右侧出现垂直滚动条，任何控件都不会被窗口截断；
  内容宽度会自动适应面板，不出现横向滚动条。
- **分组可折叠**：点击分组标题（**选中的平面** / **金线参数** / **输出选项**）即可折叠或展开，
  标题前的 **▾** 表示展开、**▸** 表示折叠。屏幕空间不足时可收起不关心的分组。
  折叠状态会被记住（立即保存，无需点 OK；「恢复默认值」不会重置它）。

> 20 µm 的金线在整机尺度（几十毫米）下几乎不可见，所以默认**只生成中心线**；
> 需要真实实体时勾选“生成金线实体”。
>
> 若选中的面位于 `PartDesign::Body` 内，Report view 会出现
> `Link(s) to object(s) ... go out of the allowed scope` 的**警告**（非错误），几何结果不受影响；
> 面板会自动检测并在顶部显示橙色提示，命令也会在 Report view 输出同样的中文说明。

### 参数化修改

生成后可直接在**属性编辑器**里改 `WireDiameter`、`Clearance`、`PlaneRotation`、`PeakRatio`、`RiseRatio`、`FallRatio`、`MakeSolid`、`ShowCentreline`、`MakeBalls`、`BallDiameter` 等，几何会自动重建；也可以改 `Face1` / `Face2` 换用其他平面。

## 4. 脚本 / 控制台用法

几何核心不依赖 GUI，可直接调用：

```python
import sys
sys.path.append(r"C:\Users\<you>\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder")

import FreeCAD as App
from WireBonder import core

doc = App.ActiveDocument
face1 = doc.getObject("Pad1").Shape.Faces[1]   # 任意一个面
face2 = doc.getObject("Pad2").Shape.Faces[1]

result = core.compute_from_faces(
    face1, face2,
    wire_diameter=0.02,   # 20 µm
    clearance=0.5,        # 净空高度 500 µm
    peak_ratio=0.42,      # 拱顶位置比例
    rise_ratio=0.60,      # 出线陡升比例
    fall_ratio=0.20,      # 落线高度比例
    make_solid=False,     # 只算中心线
    make_balls=True,      # 生成焊球
    ball_diameter=0.05,   # 焊球直径 50 µm
)
print(result["frame"].length)      # 两质心距离
print(result["centre_line"])       # 中心线 Wire
print(result["solid"])             # 金线实体 Solid（make_solid=True 时）
print(result["balls"])             # 两个焊球 Solid
print(result["plane"])             # 平分平面 Face（辅助面用）
```

也可以用 `WireBonder.features.WireBondFeature` 直接创建参数化对象：

```python
from WireBonder import features

obj = doc.addObject("Part::FeaturePython", "WireBond")
features.WireBondFeature(obj)
features.ViewProviderWireBond(obj.ViewObject)   # 金色显示样式
obj.Face1 = (doc.getObject("Pad1"), "Face6")
obj.Face2 = (doc.getObject("Pad2"), "Face6")
obj.Clearance = "500 um"
obj.WireDiameter = "20 um"
obj.BallDiameter = "50 um"
obj.MakeBalls = True
doc.recompute()
```

## 5. 已知限制

- **金线实体放样较慢**：0.02 mm 直径、上百毫米长的管道对 OCCT 负担较大，实测约需 1 分钟；只生成中心线则几乎是瞬时的。
- **法线退化情形**：两个平面法线恰好反向（180°）时平分线不存在，插件会给出提示；此时请选择朝向一致的两个面。
- **连线与平分线平行**时平面不唯一，同样会提示。
- **净空高度的定义**是“弧顶相对两质心连线的高度”，不是相对元器件表面；需要以表面为基准时可自行换算。
- **作用域隔离提示**：面取自 `PartDesign::Body` 时，生成对象必然触发 `go out of the allowed scope` 警告（见 §3）。这是 FreeCAD 的作用域机制，插件无法消除；把焊盘改用 Part 工作台建模（`Part::Box` 等）即可避免。
- **装配体坐标系**：面取自 `App::Part` 容器内的零件时，插件会自动补偿父容器变换（`getGlobalPlacement()`），金线始终落在全局装配位置。若之后**移动了父容器**（改变 `App::Part` 的 Placement），请手动执行一次 `Ctrl` + `R` 重算以刷新几何。
- **净空高度与间距**：当净空高度大于两质心间距时，弧线会非常夸张（面板会给出橙色提醒）；注意弧高是**相对两质心连线**的，不是相对元器件表面。
- **不要对 PartDesign 的阵列特征使用变换工具**：`LinearPattern`/`LinearPattern001` 等属于“多变换特征”，PartDesign 只允许变换 additive/subtractive 特征，对它执行变换会报 `ViewProviderTransformed: Only additive and subtractive features can be transformed`。要改阵列请修改其 `Length`/`Occurrences`/`Direction` 参数；要整体移动请选中 `Body` 改 `Placement`。
- `WireBondPlane` 是**辅助面**：`Create Wire Bond` 流程生成的辅助面会自动隐藏（需要时在模型树里勾选显示）；若想直接得到可见的平分面，请使用 `Create Bisector Plane` 命令。其矩形范围自动外扩，可在属性中调整 `Margin` 与 `WidthFactor`。
- 焊球位于两个平面的质心处，直径由 `BallDiameter` 指定；它同样参与参数化重建，改直径或关闭 `MakeBalls` 即可。
- 金线实体与中心线处于同一 `Compound` 中，因此**共用一种颜色**（金色）。

## 6. 排查加载问题

1. **FreeCAD 启动日志**：用 `FreeCAD.exe --log-file "%TEMP%\fc.log"` 启动，日志中
   `Init: Initializing ...\Mod\WireBonder\.\... done` 表示插件已被发现并执行；
   若出现 `Traceback` / `Err: During initialization the error ...`，则是插件代码报错。
2. **插件自己的日志**：`<Mod>\WireBonder\wirebonder_load.log`（同时写一份到 `%TEMP%`），
   记录插件目录定位结果与 `addWorkbench` 是否成功，是排查“工作台不出现”的第一手资料。成功时形如：

   ```log
   [2026-09-21 13:14:54] no __file__ in this namespace (NameError(...)), fall back to sys.path
   [2026-09-21 13:14:54] addon_dir  = ...\Mod\WireBonder
   [2026-09-21 13:14:54] package_dir= ...\Mod\WireBonder\WireBonder
   [2026-09-21 13:14:54] icon_dir   = ...\resources\icons (exists: True)
   [2026-09-21 13:14:54] addWorkbench OK
   ```

   第一行的 `no __file__` 属**正常现象**（见下）。
3. **已经踩过的坑（二次开发时务必注意）**：
   - FreeCAD 是以 `exec(code, globals, locals)` 执行 `InitGui.py` 的，且传入的
     `globals` 与 `locals` **不是同一个字典**：命名空间里**没有 `__file__`**，
     而且**顶层函数一旦引用模块级变量就会 `NameError`**
     （模块级赋值只写进了 `locals`，函数查名字用的却是 `globals`）。
     因此本插件的全部逻辑都写在**单个函数内部**，只用局部/闭包变量。
   - PySide6（Qt6）的枚举是 `enum.Flag`，`int(QDialogButtonBox.Ok | Cancel)` 会抛
     `TypeError`，必须取 `.value`；PySide2 则可以直接 `int()`。
   - `obj.Shape` 是只读的，`obj.Shape.reverse()` 会抛 `ReferenceError: This object is immutable`；
     需先 `shape = obj.Shape.copy()` 再修改并回写。
4. 若选中的两个面位于 `PartDesign::Body` 内部，生成对象时 FreeCAD 会提示
   `Link(s) to object(s) ... go out of the allowed scope`：这是**警告而非错误**，
   几何依然正确。想彻底避免可把焊盘做成独立的 Part 对象，或把生成的对象放进与
   Body 同级的 `App::Part` 容器。

## 7. 文件结构

```text
src/                          # 插件源码 (安装时复制到 <Mod>/WireBonder)
├── Init.py                   # 非 GUI 加载入口, 同时是"插件目录"的标记
├── InitGui.py                # 工作台注册 (单函数结构, 写加载日志)
├── package.xml               # Addon Manager 元数据 (classname/icon/subdirectory)
├── README.md                 # 本文件: 插件功能/参数/脚本用法/排错
└── WireBonder/               # Python 包
    ├── __init__.py           # 版本与简介
    ├── i18n.py               # 多语言 (中文/英文, 跟随 FreeCAD 语言设置)
    ├── language_monitor.py   # 运行期语言变化监听 (切换语言无需重启)
    ├── settings.py           # 面板参数持久化 (记住上次设置)
    ├── core.py               # 几何核心（无 GUI 依赖）: 质心/法线、平分平面、打线弧、放样、焊球
    ├── features.py           # 参数化对象 WireBond / WireBondPlane + 显示样式
    ├── taskpanel.py          # 参数面板（PySide2 / PySide6 兼容）
    ├── commands.py           # FreeCAD 命令、选择校验、退化情形预检
    └── resources/icons/      # WireBonder.svg / WireBond_Create.svg / WireBond_Plane.svg
```

## 8. 多语言

插件界面文字**跟随 FreeCAD 的语言设置**：

| FreeCAD 语言 | 插件显示 |
| --- | --- |
| 中文（简体 / 任意 `zh*`） | **中文** |
| English | **英文** |
| 其它任意语言（德语、日语…） | **英文**（回退） |

语言探测顺序（[`i18n.detect_language()`](WireBonder/i18n.py)）：

1. `FreeCADGui.getLocale()` —— GUI 环境最准确，返回如 `'Chinese (Simplified)'`；
2. 用户参数 `User parameter:BaseApp/Preferences/General` 的 `Language` —— 无 GUI 也能用；
3. `PySide.QtCore.QLocale.system().name()` —— 如 `zh_CN`；
4. 全部失败 → 英文。

### 切换语言（无需重启）

在 FreeCAD 里改语言（**Edit ▸ Preferences ▸ General ▸ Language**）后**立即生效**，
工作台名称、工具栏/菜单按钮、参数面板全部随之切换，不需要重启 FreeCAD。

实现要点（[`language_monitor.py`](WireBonder/language_monitor.py)）：

- **两个信号源同时监视**：`Language` 用户参数（偏好设置对话框写入）与 `FreeCADGui.getLocale()`（GUI 实际使用的值），二者可能各自变化；
- 参数观察者 `ParamGet(...).Attach()` 提供即时回调，另有一个 1.5 s 轮询定时器兜底；
- 检测到 `Language` 参数变化时，插件调用 `FreeCADGui.setLocale()` 把新语言推给 GUI，使 FreeCAD 自身界面与插件保持一致 —— **只改参数并不会自动更新 `getLocale()`**，这是关键；
- 变化后重新注册工作台（`Gui.removeWorkbench` + `Gui.addWorkbench`）以重建菜单；
- 按钮文字需**延后一个事件循环**再设置：FreeCAD 在处理 `LanguageChange` 事件时会把 QAction 文字重置为未翻译字符串，立即设置会被覆盖，因此用 `QTimer.singleShot(0, ...)` 延后写入。

启动日志中会记录生效语言与切换动作：

```log
[2026-09-22 12:04:01] language   = zh
...
WireBond: language changed zh -> en
```

### 增加新语言 / 扩展词条

1. 打开 [`WireBonder/i18n.py`](WireBonder/i18n.py)，中文词条表 `_ZH` 以**英文原文为 key**；
2. 增加一种语言：新增 `_JA = { "Wire Bond": "ワイヤボンド", ... }`，并把它加入
   `_TRANSLATIONS` 与 `LANGUAGES`，同时在 `_normalize()` 中识别该语言代码；
3. 源码中新增的用户可见字符串一律写成 `_("English text")` 形式。

> 未翻译的条目会**自动回退为英文原文**，不会显示空白或 key。

### 控制台用法

```python
from WireBonder import i18n
print(i18n.language())          # 'zh' 或 'en'（自动探测的结果）
i18n.set_language("en")         # 临时强制英文（None 表示恢复自动探测）
print(i18n.translate("Wire Bond"))
```

## 9. 相关文档

- 项目设计文档（需求、几何算法、数据模型、架构、测试用例、踩坑记录）：[`../docs/freecad-wirebonder-prd.md`](../docs/freecad-wirebonder-prd.md)
- 安装操作文档（安装/升级/卸载/验证/排错全流程）：[`../README.md`](../README.md)

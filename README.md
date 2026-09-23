# WireBonder — FreeCAD 打线（金线）辅助插件

[English](README-en.md)

> 版本 **0.14.0** ｜ 实测环境 **FreeCAD 1.1.3 + Python 3.11.14 + PySide6 6.8.3**

## 1. 项目介绍

WireBonder 是一个 **FreeCAD 工作台插件**，用于在装配体中快速生成打线（wire bond）的金线几何，主要服务于芯片键合方案的示意与干涉检查。

**它做什么**：在 3D 视图中选中两个平面，插件自动

1. 取两个平面的**质心**与**法线**；
2. 由「质心连线方向」与「两法线的角平分方向」张成**走线平面**（即平分平面）；
3. 在该平面内画出一条连接两个质心的**打线弧**（出线扬起 → 拱顶 → 平缓落回）；
4. 按设定的**金线直径**把弧线放样成实体，并可选择在两端生成**焊球**（球形 / 圆台）。

**参数化**：金线直径、弧线控制点、出线/落线角度、走线平面偏转角、焊球形状与直径等全部是对象属性，改完自动重建几何；面板会记住上次使用的设置。界面文字跟随 FreeCAD 的语言设置，**切换语言无需重启**。

**典型用途**：芯片与基板焊盘之间的键合走线示意、弧线高度/净空的确认、多条金线之间的干涉排查。

### 功能与几何细节

几何构造规则（坐标系、每一个控制点的逻辑、插值、角度定义）、面板参数清单、脚本/控制台用法与多语言实现，**全部集中在一份文档里**：

> 👉 **[插件功能文档：`src/README.md`](src/README.md)** ｜ [English](src/README-en.md)

### 设计文档

| 文档 | 内容 |
| --- | --- |
| [`docs/freecad-wirebonder-prd.md`](docs/freecad-wirebonder-prd.md) | 产品需求、算法取舍、数据模型、修订记录 |
| [`docs/parameters.md`](docs/parameters.md) | 每一个参数的详细说明 |
| [`docs/spline-ctrl-points.md`](docs/spline-ctrl-points.md) | 弧线控制点的权威定义（规范来源） |
| [`context/agent-guide.md`](context/agent-guide.md) | 交接指南：关键决策、FreeCAD/OCC 踩坑记录 |

下面是本仓库的**工程说明**：环境、安装、调试、动态加载与文件结构。

---

## 2. 运行环境

| 项目 | 要求 | 本机实测 |
| --- | --- | --- |
| 操作系统 | Windows / Linux / macOS | Windows 10 (26200) |
| FreeCAD | 1.0 / 1.1（推荐 1.1） | 1.1.3 |
| Python | 3.8+（随 FreeCAD 内置，**不要**用系统 Python 运行插件） | 3.11.14 |
| Qt 绑定 | PySide6（FreeCAD 1.x 自带 `PySide` 兼容层） | PySide6 6.8.3 |

**无第三方依赖**：插件只使用随 FreeCAD 分发的 `FreeCAD`、`Part`、`FreeCADGui`、`PySide`，**不需要 pip 安装任何包**，也**不需要编译**（纯 Python）。

只有仓库里的离线脚本 [`scripts/`](scripts/) 需要额外用到 `matplotlib`（仅用于画示意图，与插件运行无关）。

---

## 3. 安装

### 3.0 先确认本机的 Mod（插件）目录

FreeCAD 的**用户级插件目录带版本号**，不同版本目录名不同（`v1-1`、`v1-0`、`v0.21` …）。最可靠的方法是直接在 FreeCAD 里查询 —— 打开 **View ▸ Panels ▸ Python console**，输入：

```python
import os
print(os.path.join(FreeCAD.getUserAppDataDir(), "Mod"))
```

输出即为插件应放入的目录。各平台默认位置（供参考）：

| 平台 | Mod 目录 |
| --- | --- |
| Windows | `%APPDATA%\FreeCAD\v1-1\Mod\` |
| Linux | `~/.local/share/FreeCAD/v1-1/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |

目录不存在时手动创建即可。安装后插件目录名建议就叫 **`WireBonder`**。

> ⚠ **插件目录必须同时包含 `Init.py` 与 `InitGui.py`**：FreeCAD 启动时遍历 Mod 下的每个子目录，**只有存在 `Init.py` 才会把它当作插件加载**；缺少 `Init.py` 的目录会在启动日志里被标为 `Initializing ...(Init.py not found)... ignore` 并直接跳过（已实测确认）。

### 3.1 方式 A：手动复制（推荐，最简单）

把项目里的 [`src/`](src) 目录复制到 Mod 目录下，并**重命名为 `WireBonder`**（`src` 只是本仓库的源码目录名）。

**Windows（cmd，在项目根目录执行）**

```bat
xcopy /E /I /Y src "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

**Windows PowerShell**

```powershell
Copy-Item -Recurse -Force .\src "$env:APPDATA\FreeCAD\v1-1\Mod\WireBonder"
```

**Linux / macOS**

```bash
cp -r src ~/.local/share/FreeCAD/v1-1/Mod/WireBonder
# macOS: cp -r src ~/Library/Application\ Support/FreeCAD/v1-1/Mod/WireBonder
```

### 3.2 方式 B：Addon Manager 安装（从压缩包）

1. 把插件根目录打包为 zip（zip 内**直接**包含 `InitGui.py` 与 `package.xml`，**不要**多套一层文件夹）：

   ```bat
   :: Windows
   powershell -Command "Compress-Archive -Path .\src\* -DestinationPath .\WireBonder.zip -Force"
   ```

   ```bash
   # Linux / macOS
   (cd src && zip -r ../WireBonder.zip .)
   ```

2. FreeCAD 菜单 **Tools ▸ Addon manager**，右上角下拉选择 **Install from file…**，选中 `WireBonder.zip`；
3. 按提示重启 FreeCAD。

元数据由 [`src/package.xml`](src/package.xml) 提供，其中 `<classname>WireBonderWorkbench</classname>` 必须与 [`src/InitGui.py`](src/InitGui.py) 里注册的类名一致。

### 3.3 验证安装

重启 FreeCAD 后依次检查：

1. **工作台下拉框**出现 **Wire Bonding**；
2. **工具栏**出现 `Create Wire Bond`（金色弧线图标）与 `Create Bisector Plane`（绿色平面图标）两个按钮；
3. Python 控制台应输出两项命令：

   ```python
   import FreeCADGui as Gui
   print([c for c in Gui.listCommands() if "WireBonder" in c])
   # ['WireBonder_CreatePlane', 'WireBonder_CreateWireBond']
   ```

4. **查看加载日志**（每次启动 FreeCAD 都会重新生成）：

   ```text
   <Mod>\WireBonder\wirebonder_load.log      (Windows)
   %TEMP%\wirebonder_load.log               (每个平台都有一份)
   ```

   加载成功的日志形如：

   ```log
   [2026-09-21 13:14:54] no __file__ in this namespace (NameError(...)), fall back to sys.path
   [2026-09-21 13:14:54] addon_dir  = C:\Users\Edison\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder
   [2026-09-21 13:14:54] package_dir= ...\Mod\WireBonder\WireBonder
   [2026-09-21 13:14:54] icon_dir   = ...\resources\icons (exists: True)
   [2026-09-21 13:14:54] addWorkbench OK
   ```

   - 第一行说明 FreeCAD 是以 `exec` 方式执行 `InitGui.py` 的（命名空间里没有 `__file__`），插件已自动回退到 `sys.path` 定位，属**正常现象**；
   - 出现 `addWorkbench OK` 即为注册成功；
   - 若为 `addWorkbench FAILED` 或根本没有该文件，见下一节。

### 3.4 升级与卸载

**升级**：重新执行安装覆盖同一目录，然后**重启 FreeCAD**（插件在启动时加载）。

> 覆盖后行为没变化时，先删掉安装目录里的 `__pycache__` 再重启。

**卸载**：删除 Mod 下的插件目录，重启 FreeCAD。

```bat
rmdir /s /q "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

```bash
rm -rf ~/.local/share/FreeCAD/v1-1/Mod/WireBonder
```

> 卸载只影响插件本身；已生成的金线对象保存在各自的 `.FCStd` 文档里不受影响，但会退化为普通几何，无法再参数化重建。

---

## 4. 调试

### 4.1 先看加载日志

`wirebonder_load.log` 是排查“插件到底有没有被加载”的第一现场，记录了目录定位结果、图标路径是否存在、`addWorkbench` 状态与生效语言。它由 [`src/InitGui.py`](src/InitGui.py) 在注册结束后写出，插件目录与 `%TEMP%` 各一份。

> 若**连这个日志文件都没有**，说明 `InitGui.py` 在写出日志之前就抛了异常。此时会有一份末级日志 `%TEMP%\wirebonder_boot.log`（记录完整 traceback），FreeCAD 自身启动不中断 —— 这是有意设计：插件出问题绝不拖垮 FreeCAD 启动。

想拿到 FreeCAD 自身启动过程的日志，可带 `--log-file` 启动：

```bat
FreeCAD.exe --log-file "%TEMP%\fc.log"
```

在日志中搜索 `WireBonder`：出现 `Initializing ...\Mod\WireBonder\.\... done` 表示已加载；出现 `Traceback` 或 `Err: During initialization the error ...` 则是插件报错。

### 4.2 一次性自检片段

把下面这段贴进 Python 控制台，可一次核对安装结果：

```python
import os, sys, importlib
import FreeCAD, FreeCADGui as Gui

addon = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder")
print("addon dir      :", addon, os.path.isdir(addon))
print("Init.py        :", os.path.isfile(os.path.join(addon, "Init.py")))
print("InitGui.py     :", os.path.isfile(os.path.join(addon, "InitGui.py")))
print("package.xml    :", os.path.isfile(os.path.join(addon, "package.xml")))

if addon not in sys.path:
    sys.path.append(addon)
import WireBonder
print("version        :", WireBonder.__version__)

wb = Gui.listWorkbenches().get("WireBonderWorkbench")
print("workbench      :", "registered" if wb else "NOT registered")
if wb:
    print("icon exists    :", os.path.isfile(wb.Icon))
    print("commands       :", [c for c in Gui.listCommands() if "WireBonder" in c])

log = os.path.join(addon, "wirebonder_load.log")
print("load log       :", log, os.path.isfile(log))
if os.path.isfile(log):
    print(open(log, encoding="utf-8").read().strip())
```

### 4.3 两个必须知道的坑

**① `exec` 下的 `globals` / `locals` 陷阱。**
FreeCAD 是以 `exec(code, globals, locals)` 执行 `InitGui.py` 的，且传入的 `globals` 与 `locals` **不是同一个字典**：命名空间里**没有 `__file__`**，而且**顶层函数一旦引用模块级变量就会 `NameError`**（模块级赋值只写进了 `locals`，函数查名字用的却是 `globals`）。这会让插件“静默失效”——目录正常、没有弹窗，工作台就是不出来。
本插件因此把**全部逻辑写进单个函数内部**，只用局部/闭包变量；[`src/Init.py`](src/Init.py) 也只保留最简单的顶层语句。**改动这两个文件时不要引入依赖模块级状态的顶层函数。**

**② 中文控制台编码。**
`cmd.exe` 默认 GBK，在控制台里 `print` 中文可能抛 `UnicodeEncodeError: 'gbk' codec can't encode character`。这是**控制台的问题，不是插件的问题**；把结果写进文件再读，或临时 `chcp 65001` 即可。

### 4.4 从现象定位

| 现象 | 原因与处理 |
| --- | --- |
| 工作台下拉框里没有 **Wire Bonding** | ① 目录层级不对：必须存在 `<Mod>/WireBonder/InitGui.py`，不要多套一层；② **缺少 `Init.py`** → FreeCAD 打印 `(Init.py not found)... ignore` 并跳过整个目录；③ 放错版本目录（1.1 是 `v1-1`，1.0 是 `v1-0`，0.21 是 `v0.21`）；④ 未重启 FreeCAD |
| 目录与文件都正常，工作台仍不出现 | 多为一节 4.3① 的 `exec` 命名空间陷阱；对照 `wirebonder_load.log` 与 `Traceback` 定位 |
| 命令是灰色不可点 | 必须**恰好选中两个面**。选中边、点或整个对象（无子元素）时命令会自动禁用并提示识别到的面数 |
| 弹出面板时报 `TypeError: int() argument must be ... not 'StandardButton'` | PySide6（Qt6）枚举是 `enum.Flag`，`int(QDialogButtonBox.Ok \| Cancel)` 不能直接转换，必须取 `.value`（0.1.0 已修复，升级并重启即可） |
| 图标显示为空白方块 | 确认 `WireBonder/resources/icons/*.svg` 三个文件都存在；可打印 `Gui.listWorkbenches()["WireBonderWorkbench"].Icon` 检查路径；`package.xml` 的 `<classname>` 必须与 `InitGui.py` 的类名一致 |
| 控制台 `import WireBonder` 失败 | `sys.path` 需指向**插件根目录**（即包含 `WireBonder/` 包的那一层），而不是包目录本身 |
| 面板改了参数没变化 | 触发一次重算：`Ctrl` + `R`，或执行 `FreeCAD.ActiveDocument.recompute()` |
| 界面语言不对 | 插件跟随 FreeCAD 语言设置：中文环境显示中文，其它语言（含英文）显示英文。自 v0.3.0 起切换语言**无需重启**（**Edit ▸ Preferences ▸ General ▸ Language** 改完即生效）；仍不对可看 `wirebonder_load.log` 里的 `language = zh` / `language switched zh -> en` 记录 |
| 出现 `Link(s) to object(s) ... go out of the allowed scope` | 选中的面位于 `PartDesign::Body` 内部。这是**警告而非错误**，几何结果正确；想彻底避免请把焊盘改用 Part 工作台建模 |
| 看不到金线 | 20 µm 在几十毫米尺度下几乎不可见。默认只生成中心线（金色细线）用于示意；要真实实体请勾选“生成金线实体” |
| 生成实体时卡住很久 | 细直径 + 长路径的 OCCT 放样较耗时（实测 20 µm × 100 mm 约 1 分钟）。建议先用中心线确定走向，最后再生成实体 |

> 与**几何/参数语义**有关的问题（角度基准、控制点含义、最高点过冲、焊球尺寸等）请查阅 [`src/README.md`](src/README.md)；更细的排查记录见 [`context/agent-guide.md`](context/agent-guide.md) 第 4 节。

---

## 5. 动态加载

插件代码是在 **FreeCAD 启动时**加载的，所以改完源码**默认需要重启**。开发期不想反复重启时，可以用下面两种方式。

### 5.1 当前会话临时加载（免重启试用，不写入 Mod 目录）

在 Python 控制台执行：

```python
import os, sys
addon = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder")
if addon not in sys.path:
    sys.path.append(addon)

import WireBonder.commands          # 注册两个命令
import FreeCADGui as Gui
Gui.activateWorkbench("WireBonderWorkbench")
```

工作台与工具栏会立即出现在当前会话中。也可以把 `addon` 指向仓库里的 [`src/`](src) 目录，直接从源码目录试用，无需先安装。

> 这种方式**只对当前会话有效**，下次启动仍需正式安装才会自动加载。

### 5.2 热重载已安装的模块

改完源码 → 先同步到 Mod 目录（方式 A 的手动复制，或自行用脚本覆盖）→ 再在控制台重载：

```python
import sys, importlib
if r"C:\Users\<you>\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder" not in sys.path:
    sys.path.append(r"C:\Users\<you>\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder")

import WireBonder
for name in ("i18n", "settings", "core", "features", "taskpanel", "commands"):
    module = getattr(WireBonder, name, None) or importlib.import_module("WireBonder." + name)
    importlib.reload(module)
print("reloaded", WireBonder.__version__)
```

要点：

- **重载顺序**：`core` / `settings` / `i18n` 是底层，`features` / `taskpanel` / `commands` 依赖它们，按上面的顺序重载；
- **注册型模块**（`commands`、`InitGui`）重载后，菜单/工具栏仍可能指向旧对象。`Gui.addWorkbench` 对同名工作台**不会覆盖**，所以要让新按钮生效，最省事的做法是**重新执行一遍 [`src/InitGui.py`](src/InitGui.py)** —— 它内部的 `register_workbench()` 已经封装了「有则 `removeWorkbench`、无则新增」的完整流程（运行期语言切换复用的就是它）：
  ```python
  import os, FreeCAD
  init_gui = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder", "InitGui.py")
  exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"))
  ```
  重新执行会覆盖 `wirebonder_load.log`，可借此确认这一次注册也是 `addWorkbench OK`；
- **`__pycache__` 会干扰**：怀疑加载的是旧字节码时，删掉安装目录下的所有 `__pycache__` 再重试；
- **旧对象仍用旧代码**：`reload` 只影响**之后新建**的对象；已经存在于文档里的 `WireBond` 对象在下次 `recompute()` 时才会走新实现（其类的 `execute()` 已随模块重载更新，但如果属性结构变了需要重新创建对象）；
- **改 `Init.py` / `InitGui.py` 后无法用 reload 完全复现启动环境**，涉及这两个文件请直接重启 FreeCAD。

---

## 6. 文件结构

### 6.1 仓库结构

```text
wire-bonder/
├── README.md                      # 本文件：项目介绍 / 环境 / 安装 / 调试 / 动态加载 / 文件结构
├── README-en.md                   # 本文件的英文翻译版本
├── context/
│   └── agent-guide.md             # 交接指南：关键决策、踩坑记录
├── data/                          # 参考图与生成的对照图
├── docs/
│   ├── freecad-wirebonder-prd.md  # 设计文档（需求/算法/数据模型/修订记录）
│   ├── parameters.md              # 参数详细说明
│   ├── spline-ctrl-points.md      # 弧线控制点规范
│   └── images/
├── scripts/                       # 独立 Python 工具，均不依赖 FreeCAD
│   ├── wirebond_sketch.py         # 画控制点示意图（中/英双语，见 --help）
│   └── draw_two_squares.py
└── src/                           # ★ 插件源码，安装时整体复制到 Mod 目录
    ├── Init.py
    ├── InitGui.py
    ├── package.xml
    ├── README.md / README-en.md   # 插件功能与几何文档（中 / 英）
    ├── wirebond-sketch-zh.png     # 示意图（中文标注）
    ├── wirebond-sketch-en.png     # 示意图（英文标注）
    └── WireBonder/
        ├── __init__.py
        ├── core.py
        ├── features.py
        ├── taskpanel.py
        ├── commands.py
        ├── settings.py
        ├── i18n.py
        ├── language_monitor.py
        └── resources/icons/*.svg
```

### 6.2 安装后的插件目录

```text
<Mod>/
└── WireBonder/                    # 插件根目录（名字建议就叫 WireBonder）
    ├── Init.py                    # 必须有
    ├── InitGui.py                 # 必须有
    ├── package.xml
    ├── README.md / README-en.md
    ├── wirebonder_load.log        # 首次加载后自动生成，用于排查
    └── WireBonder/                # Python 包
        ├── __init__.py
        ├── core.py
        ├── features.py
        ├── taskpanel.py
        ├── commands.py
        ├── settings.py
        ├── i18n.py
        ├── language_monitor.py
        └── resources/icons/*.svg
```

### 6.3 各文件职责

| 文件 | 作用 |
| --- | --- |
| [`src/Init.py`](src/Init.py) | 非 GUI 加载入口；同时是“这是一个插件目录”的标记（缺失会被 FreeCAD 跳过），并把插件根目录加入 `sys.path`，使控制台可直接 `import WireBonder` |
| [`src/InitGui.py`](src/InitGui.py) | 注册 `WireBonderWorkbench` 工作台、工具栏与菜单；逻辑全部写在单个函数内（规避 `exec` 下 `globals`/`locals` 陷阱），并把加载过程写入 `wirebonder_load.log` |
| [`src/package.xml`](src/package.xml) | Addon Manager 元数据（名称、版本、图标、工作台类名、`subdirectory`） |
| [`src/WireBonder/core.py`](src/WireBonder/core.py) | 几何核心，**无 GUI 依赖**：质心/法线、走线坐标系、弧线控制点、样条、放样、焊球 |
| [`src/WireBonder/features.py`](src/WireBonder/features.py) | 参数化对象 `WireBond` / `WireBondPlane` 及其显示样式（金色金线、半透明辅助面） |
| [`src/WireBonder/taskpanel.py`](src/WireBonder/taskpanel.py) | 参数输入面板（PySide2 / PySide6 兼容，使用 FreeCAD 原生 `Gui::QuantitySpinBox`） |
| [`src/WireBonder/commands.py`](src/WireBonder/commands.py) | FreeCAD 命令、选择校验与退化情形预检 |
| [`src/WireBonder/settings.py`](src/WireBonder/settings.py) | 面板参数的持久化（FreeCAD 用户参数） |
| [`src/WireBonder/i18n.py`](src/WireBonder/i18n.py) | 中英词条（英文原文即 msgid） |
| [`src/WireBonder/language_monitor.py`](src/WireBonder/language_monitor.py) | 运行期语言切换监听，无需重启 |
| [`src/WireBonder/resources/icons/*.svg`](src/WireBonder/resources/icons) | 工作台与两个命令的图标 |
| [`scripts/wirebond_sketch.py`](scripts/wirebond_sketch.py) | 离线示意图脚本（中/英/双语，`-l` 选择语言，`-o` 指定输出） |

---

## 7. 开发约定

- 源码改动后**必须重新同步**到 Mod 目录，并重启 FreeCAD 或按第 5 节热重载，否则看到的是旧代码；
- 用户可见的字符串一律写成 `_("English text")` 形式，词条表在 [`src/WireBonder/i18n.py`](src/WireBonder/i18n.py)，新增语言的方法见 [`src/README.md`](src/README.md) 的「多语言」章节；
- 版本号需同时更新 [`src/WireBonder/__init__.py`](src/WireBonder/__init__.py) 的 `__version__` 与 [`src/package.xml`](src/package.xml) 的 `<version>`；
- 修改 [`src/Init.py`](src/Init.py) / [`src/InitGui.py`](src/InitGui.py) 时务必遵守“顶层不放依赖模块级状态的函数”这条约束。

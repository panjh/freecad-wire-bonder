# WireBonder 插件安装操作文档

FreeCAD 打线（金线）辅助插件：**选中两个平面 → 自动构造平分平面 → 沿两个质心连线生成金线**，金线直径与净空高度可设置。

- 插件源码目录：[`src/`](src/README.md)
- 设计文档：[`docs/freecad-wirebonder-prd.md`](docs/freecad-wirebonder-prd.md)
- 插件入口文件：[`src/InitGui.py`](src/InitGui.py)
- 非 GUI 入口：[`src/Init.py`](src/Init.py)
- 几何核心：[`src/WireBonder/core.py`](src/WireBonder/core.py)

---

## 1. 前置条件

| 项目 | 要求 | 本机实测 |
| --- | --- | --- |
| FreeCAD | 1.0 / 1.1（推荐 1.1） | 1.1.3 |
| Python | 3.8+（随 FreeCAD 内置） | 3.11.14 |
| Qt 绑定 | PySide6（FreeCAD 1.x 自带 `PySide` 兼容层） | PySide6 6.8.3 |

插件只用到 `FreeCAD`、`Part`、`FreeCADGui`、`PySide` 这些随 FreeCAD 分发的模块，**不需要额外 pip 安装任何依赖**。

---

## 2. 第一步：确认本机的 Mod（插件）目录

FreeCAD 的用户级插件目录**带版本号**，不同版本目录名不同（`v1-1`、`v1-0`、`v0.21` …）。最可靠的方法是直接在 FreeCAD 里查询。

打开 FreeCAD，菜单 **View ▸ Panels ▸ Python console**，输入：

```python
import os
print(os.path.join(FreeCAD.getUserAppDataDir(), "Mod"))
```

输出即为需要放入插件的目录，例如本机：

```sh
C:\Users\Edison\AppData\Roaming\FreeCAD\v1-1\Mod
```

各平台的默认位置（供参考）：

| 平台 | Mod 目录 |
| --- | --- |
| Windows | `%APPDATA%\FreeCAD\v1-1\Mod\` |
| Linux | `~/.local/share/FreeCAD/v1-1/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |

> 目录不存在时先手动创建即可。
>
> ⚠ **插件目录必须同时包含 `Init.py` 与 `InitGui.py`**：FreeCAD 启动时遍历 Mod 下的每个子目录，只有存在 `Init.py` 才会把它当作插件加载；缺少 `Init.py` 的目录会在启动日志里被标为
> `Initializing ...(Init.py not found)... ignore` 而直接跳过（已实测确认）。

---

## 3. 第二步：安装

### 方式 A：手动复制（推荐，最简单）

把项目里的 [`src/`](src/README.md) 目录复制到 Mod 目录下，并**重命名为 `WireBonder`**（`src` 是本项目的源码目录名，安装后的插件目录名建议就叫 `WireBonder`）。

#### Windows（在项目根目录执行

```bat
xcopy /E /I /Y src "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

#### Windows PowerShell

```powershell
Copy-Item -Recurse -Force .\src "$env:APPDATA\FreeCAD\v1-1\Mod\WireBonder"
```

#### Linux / macOS

```bash
cp -r src ~/.local/share/FreeCAD/v1-1/Mod/WireBonder
# macOS: cp -r src ~/Library/Application\ Support/FreeCAD/v1-1/Mod/WireBonder
```

复制完成后的目录结构应为：

```text
<Mod>/
└── WireBonder/                 <- 插件根目录 (名字建议就叫 WireBonder)
    ├── Init.py                 <- 必须有, 缺少它 FreeCAD 会跳过整个目录
    ├── InitGui.py              <- 必须有, 工作台在这里注册
    ├── package.xml             <- Addon Manager 元数据 (工作台类名/图标)
    ├── README.md
    ├── wirebonder_load.log     <- 首次加载后自动生成, 用于排查
    └── WireBonder/             <- Python 包
        ├── __init__.py
        ├── core.py
        ├── features.py
        ├── taskpanel.py
        ├── commands.py
        └── resources/icons/*.svg
```

### 方式 B：Addon Manager 安装（从压缩包）

1. 把插件根目录打包为 zip（zip 内**直接**包含 `InitGui.py` 与 `package.xml`，不要多套一层文件夹）：

   ```bat
   :: Windows
   powershell -Command "Compress-Archive -Path .\src\* -DestinationPath .\WireBonder.zip -Force"
   ```

   ```bash
   # Linux / macOS
   (cd src && zip -r ../WireBonder.zip .)
   ```

2. FreeCAD 菜单 **Tools ▸ Addon manager**，右上角下拉选择 **Install from file…**，选中 `WireBonder.zip`。
3. 安装完成后按提示重启 FreeCAD。

### 方式 C：免重启试用（当前会话临时加载）

不想重启 FreeCAD 时，在 Python 控制台执行：

```python
import os, sys
addon = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder")
if addon not in sys.path:
    sys.path.append(addon)

import WireBonder.commands          # 注册两个命令
import FreeCADGui as Gui
Gui.activateWorkbench("WireBonderWorkbench")
```

工作台与工具栏会立即出现在当前会话中；但**下次启动仍需上面的正式安装**才会自动加载。

### 方式 D：脚本安装（bash / msys2 / Linux / macOS）

项目根目录的 [`install.sh`](install.sh) 会自动定位 Mod 目录并完成安装：

```bash
./install.sh
```

脚本内容就是两条命令，核心是 **`cp -rfT`**：

```bash
DEST="$(ls -d "${APPDATA:-$HOME}"/FreeCAD/*/Mod | head -n 1)/WireBonder"
mkdir -p "$DEST"
cp -rfT src "$DEST"
```

**`-T`（GNU 的 `--no-target-directory`）是关键**：它让 `cp` 把目标当作普通目录处理，
于是把 `src` 的**内容**复制进 `WireBonder`，而不是在目标已存在时创建 `WireBonder/src`。
不加 `-T` 时每执行一次就会多嵌一层。

不使用 `-T` 的等效写法：给源路径加 `/.` 后缀。

```bash
cp -rf src/. "$DEST/"      # 与 cp -rfT src "$DEST" 等价
```

> 注意：`cp -T` 是 GNU coreutils 的扩展，在 Linux / msys2 / cygwin 上可用；
> BSD/macOS 的 `cp` 没有 `-T`，请用 `src/.` 那种写法。

> 注意：这种方式加载的是 `sys.path` 上已安装目录里的代码，改完源码后记得重新同步安装目录。

---

## 4. 第三步：验证安装

重启 FreeCAD 后依次检查：

1. **工作台下拉框**出现 **Wire Bonding**（Tooltip：由两个平面构造平分平面，并生成打线弧）。
2. **Python 控制台**执行以下检查，应输出两项命令：

   ```python
   import FreeCADGui as Gui
   print([c for c in Gui.listCommands() if "WireBonder" in c])
   # ['WireBonder_CreatePlane', 'WireBonder_CreateWireBond']
   ```

3. **工具栏**位于菜单栏下：选择 `Wire Bonding` 工作台后，会出现 `Create Wire Bond` 与 `Create Bisector Plane` 两个按钮（金色弧线图标 / 绿色平面图标）。

4. **查看插件加载日志**（每次启动 FreeCAD 都会重新生成）：

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

   - 第一行说明 FreeCAD 是以 `exec` 方式执行 `InitGui.py` 的（没有 `__file__`），插件已自动回退到 `sys.path` 定位，属**正常现象**；
   - 出现 `addWorkbench OK` 即为注册成功；
   - 若日志里是 `addWorkbench FAILED` 或根本没有该文件，则结合下一节排查。

本机实测结果：工作台 `WireBonderWorkbench` 注册成功，`MenuText = "Wire Bonding"`，图标路径解析正常，两个命令在激活工作台后成功注册，工具栏组 `Wire Bonding` 包含这两个命令，加载日志以 `addWorkbench OK` 结尾。

---

## 5. 首次使用

1. 选中**两个平面**：在 3D 视图中按住 `Ctrl` 点击两个面（可来自同一实体，也可来自两个对象）；
2. 点击 **Wire Bonding ▸ Create Wire Bond**；
3. 面板中填写参数：

   | 参数 | 默认 | 说明 |
   | --- | --- | --- |
   | 金线直径 | 20 µm | 放样截面直径 |
   | 净空高度 | 500 µm | 弧顶**相对两质心连线**的高度（面板以 µm 输入） |
   | 走线平面偏转角 | 0° | 走线平面绕两质心连线的偏转角（−180°~180°）；0° 与原平分平面完全重合 |
   | 拱顶位置比例 | 0.42 | 拱顶位置占连线长度比例 |
   | 出线陡升比例 | 0.60 | 起点陡升点高度比例 |
   | 落线高度比例 | 0.20 | 落线姿态控制 |
   | 焊球直径 | 50 µm | 两个焊点处焊球（bond ball）的直径 |
   | 生成金线实体 | 不勾选 | 勾选后生成真实直径实体（较慢） |
   | 同时显示中心线 | 勾选 | 便于在小直径下看清走线 |
   | 生成焊球 | 勾选 | 在两个质心处生成焊球 |
   | 创建平分辅助面 | 不勾选 | 平分辅助面（构造参考，生成后自动隐藏）；**默认不创建**以控制对象数量 |

4. 点击 **OK**，生成 `WireBond`（金线 + 焊球，金色）；平分面作为**辅助面**一并创建并自动隐藏；
5. 之后可在**属性编辑器**里随时修改 `WireDiameter`、`Clearance`、`PeakRatio`、`MakeBalls`、`BallDiameter` 等，几何会自动重建。

> 若选中的面属于 `PartDesign::Body`，创建时 Report view 会出现
> `Link(s) to object(s) ... go out of the allowed scope` 提示：这是**警告**，几何结果不受影响。

---

## 6. 升级与卸载

**升级**：用相同目录覆盖即可（方式 A 重复执行一次 xcopy），然后**重启 FreeCAD**（插件代码在启动时加载，重启后才会用上新版本）。

```bat
xcopy /E /I /Y src "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

> 若覆盖后行为没变化，可先删除安装目录里的 `__pycache__` 再重启。

**卸载**：删除 Mod 下的插件目录，重启 FreeCAD。

```bat
rmdir /s /q "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

```bash
rm -rf ~/.local/share/FreeCAD/v1-1/Mod/WireBonder
```

> 卸载只影响插件本身；已经用插件生成的金线对象保存在各自的 `.FCStd` 文档里，不受影响（但会变成普通几何，无法再参数化重建）。

---

## 7. 常见问题排查

| 现象 | 原因与处理 |
| --- | --- |
| 工作台下拉框里没有 **Wire Bonding** | ① 目录名/层级不对：必须存在 `<Mod>/WireBonder/InitGui.py`，不要多套一层；② **缺少 `Init.py`**——FreeCAD 会打印 `(Init.py not found)... ignore` 并跳过整个目录；③ 放错了版本目录（1.1 是 `v1-1`，1.0 是 `v1-0`，0.21 是 `v0.21`）；④ 未重启 FreeCAD |
| 目录与文件都正常，工作台仍不出现 | FreeCAD 是以 **`exec(code, globals, locals)`** 执行 `InitGui.py` 的，且传入的 `globals` 与 `locals` **不是同一个字典**：命名空间里**没有 `__file__`**，而且**顶层函数一旦引用模块级变量就会 `NameError`**（模块级赋值只写进了 `locals`，函数查名字用的却是 `globals`），插件因此“静默失效”——目录正常、无弹窗，工作台就是不出来。本插件已改为把全部逻辑放进**单个函数内部**、只用局部/闭包变量来规避 |
| 如何确认插件到底有没有被加载 | ① 打开 `<Mod>\WireBonder\wirebonder_load.log`（每次启动都会写，含目录定位结果与 `addWorkbench` 状态，`%TEMP%` 下也有一份）；② 用 `FreeCAD.exe --log-file "%TEMP%\fc.log"` 启动，在日志里搜 `WireBonder`：`Initializing ...\Mod\WireBonder\.\... done` 表示已加载，出现 `Traceback` / `Err: During initialization the error ...` 则是插件报错 |
| 弹出面板时报 `TypeError: int() argument must be ... not 'StandardButton'` | PySide6（Qt6）的枚举是 `enum.Flag`，`int(QDialogButtonBox.Ok \| Cancel)` 不能直接转换，必须取 `.value`。已在 0.1.0 修复；升级插件并重启即可 |
| 生成时提示 `Link(s) to object(s) ... go out of the allowed scope` | 选中的面位于 `PartDesign::Body` 内部。这是**警告而非错误**，几何结果依然正确；插件面板与 Report view 都会给出中文说明。想彻底避免请把焊盘改用 Part 工作台建模（把对象放进与 Body 同级的 `App::Part` 并不能消除，因为 Body 是更内层的作用域） |
| 提示 `ViewProviderTransformed: Only additive and subtractive features can be transformed` | 对 PartDesign 的**阵列特征**（`LinearPattern` / `LinearPattern001` 等）使用了变换工具。这类“多变换特征”不允许被变换：请改其 `Length` / `Occurrences` / `Direction` 参数，或选中 `Body` 修改 `Placement`。**该错误与插件无关** |
| 命令是灰色不可点 | 必须**恰好选中两个面**。若选中了边、点或整个对象（没有子元素），命令会自动禁用并弹窗提示当前识别到的面数 |
| 提示“两个平面的法线互成 180 度” | 两个面朝向相反，平分线不存在。请选择**朝向一致**的两个面（例如两个焊盘的顶面） |
| 提示“质心连线方向与法线平分线平行” | 该组合下平面不唯一，属于退化情形；换一组面或调整其中一个面的朝向 |
| 看不到金线 | 20 µm 在几十毫米尺度下几乎不可见，属正常现象。默认只生成中心线（金色细线）用于示意；要真实实体请勾选“生成金线实体” |
| 找不到平分平面对象 | 它是**辅助面**，`Create Wire Bond` 生成后会自动隐藏（对象仍在模型树中，勾选即可显示）。想直接得到可见平面请用 `Create Bisector Plane` 命令 |
| 金线画到模型之外、起点位置明显不对 | v0.1.2 之前未处理**装配体坐标系**：面取自 `App::Part` 容器内的零件时，质心按局部坐标计算（实测偏差可达数毫米）。已修复（`core.global_face()` 补偿父容器变换）；升级插件并重启后重新生成即可。面板现在显示**全局质心**与**两质心间距 L**，便于核对 |
| 面板提示“净空高度大于两质心间距” | 两个焊盘离得很近（例如 L = 0.393 mm）而净空高度是 500 µm 时，弧线会显得非常夸张。请减小净空高度，或确认是否选错了面 |
| 焊球太大/太小 | 在面板“焊球直径”或属性 `BallDiameter` 中调整（默认 100 µm）；不需要时取消勾选“生成焊球”或关闭 `MakeBalls` |
| 生成实体时卡住很久 | 细直径 + 长路径的 OCCT 放样较耗时（实测 20 µm × 100 mm 约 1 分钟）。建议先用中心线确定走向，最后再生成实体；或临时放大直径试算 |
| 图标显示为空白方块 | 确认 `WireBonder/resources/icons/*.svg` 三个文件都存在；必要时在控制台打印 `Gui.listWorkbenches()["WireBonderWorkbench"].Icon` 检查路径。`package.xml` 的 `<classname>` 也必须与 `InitGui.py` 的类名一致 |
| 面板修改参数后没变化 | 触发一次重算：`Ctrl` + `R`，或在 Python 控制台执行 `FreeCAD.ActiveDocument.recompute()` |
| 控制台 `import WireBonder` 失败 | `sys.path` 需要指向**插件根目录**（即包含 `WireBonder/` 包的那一层），而不是包目录本身 |
| 界面语言不是中文（或不是英文） | 插件**跟随 FreeCAD 的语言设置**：中文环境显示中文，其它语言（含英文）显示英文。自 v0.3.0 起**切换语言无需重启**——在 **Edit ▸ Preferences ▸ General ▸ Language** 改完即生效（工作台名、工具栏/菜单按钮、参数面板全部随之切换）。仍不对时可查看 `wirebonder_load.log` 里的 `language = zh`/`en` 与 `language switched zh -> en` 记录。旧版对象在属性编辑器中保留其创建时的属性描述文本，属正常现象 |

---

## 8. 附：安装检查片段

复制到 Python 控制台一次性核对安装结果：

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
try:
    import WireBonder.core as core
    importlib.reload(core)
    print("core.py        : OK (version", WireBonder.__version__ + ")")
    print("defaults       : clearance =", core.DEFAULT_CLEARANCE,
          "mm | ball dia =", core.DEFAULT_BALL_DIAMETER, "mm")
except Exception as exc:
    print("core.py        : FAILED ->", exc)

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

预期输出（本机实测）：

```log
addon dir      : C:\Users\<user>\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder True
Init.py        : True
InitGui.py     : True
package.xml    : True
core.py        : OK
defaults       : clearance = 10.0 mm | ball dia = 0.1 mm
workbench      : registered
icon exists    : True
commands       : ['WireBonder_CreatePlane', 'WireBonder_CreateWireBond']
load log       : ...\Mod\WireBonder\wirebonder_load.log True
[2026-09-21 13:14:54] ... addWorkbench OK
```

---

## 9. 插件文件清单

| 文件 | 作用 |
| --- | --- |
| `Init.py` | 非 GUI 加载入口；同时是“这是一个插件目录”的标记（缺失会被 FreeCAD 跳过），并把插件根目录加入 `sys.path` |
| `InitGui.py` | 注册 `WireBonderWorkbench` 工作台、工具栏与菜单；全部逻辑写在单个函数内（规避 FreeCAD `exec` 下的 `globals`/`locals` 陷阱），并把加载过程写入 `wirebonder_load.log` |
| `package.xml` | Addon Manager 元数据（名称、版本、图标、工作台类名、`subdirectory`） |
| `WireBonder/core.py` | 几何核心（无 GUI 依赖）：质心/法线、平分平面坐标系、打线弧控制点、样条、放样、焊球 |
| `WireBonder/features.py` | 参数化对象 `WireBond` / `WireBondPlane` 及其显示样式（金色金线、半透明辅助面） |
| `WireBonder/taskpanel.py` | 参数输入面板（PySide2 / PySide6 兼容） |
| `WireBonder/commands.py` | FreeCAD 命令、选择校验与退化情形预检 |
| `WireBonder/resources/icons/*.svg` | 工作台与命令图标 |
| `README.md` | 插件功能、几何构造规则、参数、脚本用法与排错说明 |

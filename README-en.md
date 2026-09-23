# WireBonder — FreeCAD wire bonding (gold wire) addon

[中文](README.md)

> Version **0.14.0** ｜ tested on **FreeCAD 1.1.3 + Python 3.11.14 + PySide6 6.8.3**

## 1. Project overview

WireBonder is a **FreeCAD workbench addon** that quickly builds the gold-wire geometry of a wire bond inside an assembly; it is aimed at illustrating chip bonding layouts and checking for collisions.

**What it does** — select two faces in the 3D view and the addon automatically

1. takes the **centroid** and the **normal** of both faces;
2. spans the **loop plane** (that is, the bisector plane) from "the direction of the centroid-to-centroid line" and "the angular bisector of the two normals";
3. draws, inside that plane, a **wire loop** joining the two centroids (rising out of the pad → apex → gently descending back);
4. sweeps the loop with the configured **wire diameter** into a solid, optionally growing a **bond ball** (sphere / frustum) at either end.

**Parametric** — wire diameter, loop control points, rise/fall angles, loop plane rotation and ball shape/diameter are all object properties; the geometry rebuilds as soon as one of them changes, and the panel remembers the settings you used last. The UI language follows FreeCAD's language setting, and **switching it needs no restart**.

**Typical uses** — illustrating the bond trajectory between chip and substrate pads, confirming loop height / clearance, and hunting for collisions between neighbouring wires.

### Function and geometry details

The geometry construction rules (the frame, the logic of every control point, interpolation, the definition of the angles), the full list of panel parameters, the script/console usage and the localisation implementation are **all kept in one document**:

> 👉 **[Addon documentation: `src/README-en.md`](src/README-en.md)** ｜ [中文](src/README.md)

Figure: [`src/wirebond-sketch-en.png`](src/wirebond-sketch-en.png) (the control points, side by side), produced by the standalone script [`scripts/wirebond_sketch.py`](scripts/wirebond_sketch.py) — it runs on its own and does not need FreeCAD.

### Design documents

| Document | Contents |
| --- | --- |
| [`docs/freecad-wirebonder-prd.md`](docs/freecad-wirebonder-prd.md) | Product requirements, algorithm trade-offs, data model, revision log |
| [`docs/parameters.md`](docs/parameters.md) | A detailed description of every parameter |
| [`docs/spline-ctrl-points.md`](docs/spline-ctrl-points.md) | The authoritative definition of the loop control points (the source of the specification) |
| [`context/agent-guide.md`](context/agent-guide.md) | Handover guide: key decisions, FreeCAD/OCC pitfalls |

What follows is the **engineering documentation** of this repository: requirements, installation, debugging, dynamic loading and the file structure.

---

## 2. Requirements

| Item | Requirement | Tested with |
| --- | --- | --- |
| Operating system | Windows / Linux / macOS | Windows 10 (26200) |
| FreeCAD | 1.0 / 1.1 (1.1 recommended) | 1.1.3 |
| Python | 3.8+ (bundled with FreeCAD — do **not** run the addon with a system Python) | 3.11.14 |
| Qt binding | PySide6 (FreeCAD 1.x ships a `PySide` compatibility layer) | PySide6 6.8.3 |

**No third-party dependencies**: the addon only uses `FreeCAD`, `Part`, `FreeCADGui` and `PySide`, all of which ship with FreeCAD — **no `pip install` of any kind** and **nothing to compile** (pure Python).

Only the offline scripts under [`scripts/`](scripts/) additionally need `matplotlib` (used for drawing the figure only, unrelated to running the addon).

---

## 3. Installation

### 3.0 Find your Mod (addon) directory first

FreeCAD's **user-level addon directory carries a version number**, and the directory name differs per release (`v1-1`, `v1-0`, `v0.21`, …). The most reliable way is to ask FreeCAD itself — open **View ▸ Panels ▸ Python console** and run:

```python
import os
print(os.path.join(FreeCAD.getUserAppDataDir(), "Mod"))
```

The output is the directory the addon has to go into. Default locations per platform, for reference:

| Platform | Mod directory |
| --- | --- |
| Windows | `%APPDATA%\FreeCAD\v1-1\Mod\` |
| Linux | `~/.local/share/FreeCAD/v1-1/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |

Create the directory by hand if it does not exist. After installation the addon directory should be named **`WireBonder`**.

> ⚠ **The addon directory must contain both `Init.py` and `InitGui.py`**: at start-up FreeCAD walks every sub-directory of Mod and **only treats it as an addon when `Init.py` is present**; a directory without `Init.py` is logged as `Initializing ...(Init.py not found)... ignore` and skipped outright (verified in practice).

### 3.1 Option A: manual copy (recommended, simplest)

Copy the repository's [`src/`](src) directory into the Mod directory and **rename it to `WireBonder`** (`src` is merely this repository's source directory name).

**Windows (cmd, run from the repository root)**

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

### 3.2 Option B: Addon Manager (from an archive)

1. Pack the addon root into a zip (the zip must contain `InitGui.py` and `package.xml` **directly** — do **not** add an extra folder level):

   ```bat
   :: Windows
   powershell -Command "Compress-Archive -Path .\src\* -DestinationPath .\WireBonder.zip -Force"
   ```

   ```bash
   # Linux / macOS
   (cd src && zip -r ../WireBonder.zip .)
   ```

2. FreeCAD menu **Tools ▸ Addon manager**, pick **Install from file…** from the drop-down in the top-right corner and select `WireBonder.zip`;
3. Restart FreeCAD when prompted.

The metadata comes from [`src/package.xml`](src/package.xml), whose `<classname>WireBonderWorkbench</classname>` must match the class name registered in [`src/InitGui.py`](src/InitGui.py).

### 3.3 Verifying the installation

After restarting FreeCAD, check in turn:

1. the **workbench selector** shows **Wire Bonding**;
2. the **toolbar** shows the two buttons `Create Wire Bond` (gold loop icon) and `Create Bisector Plane` (green plane icon);
3. the Python console should list two commands:

   ```python
   import FreeCADGui as Gui
   print([c for c in Gui.listCommands() if "WireBonder" in c])
   # ['WireBonder_CreatePlane', 'WireBonder_CreateWireBond']
   ```

4. **inspect the load log** (rewritten on every FreeCAD start):

   ```text
   <Mod>\WireBonder\wirebonder_load.log      (Windows)
   %TEMP%\wirebonder_load.log                (one copy on every platform)
   ```

   A successful load looks like this:

   ```log
   [2026-09-21 13:14:54] no __file__ in this namespace (NameError(...)), fall back to sys.path
   [2026-09-21 13:14:54] addon_dir  = C:\Users\Edison\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder
   [2026-09-21 13:14:54] package_dir= ...\Mod\WireBonder\WireBonder
   [2026-09-21 13:14:54] icon_dir   = ...\resources\icons (exists: True)
   [2026-09-21 13:14:54] addWorkbench OK
   ```

   - the first line shows that FreeCAD executes `InitGui.py` through `exec` (there is no `__file__` in the namespace) and that the addon fell back to locating itself through `sys.path` — that is **normal**;
   - `addWorkbench OK` means the registration succeeded;
   - if it says `addWorkbench FAILED`, or the file does not exist at all, read the next section.

### 3.4 Upgrading and uninstalling

**Upgrade**: run the installation again to overwrite the same directory, then **restart FreeCAD** (the addon is loaded at start-up).

> If the behaviour does not change after overwriting, delete the `__pycache__` inside the installed directory and restart.

**Uninstall**: delete the addon directory under Mod and restart FreeCAD.

```bat
rmdir /s /q "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

```bash
rm -rf ~/.local/share/FreeCAD/v1-1/Mod/WireBonder
```

> Uninstalling only affects the addon itself; the gold wires you already created live in their own `.FCStd` documents and survive — but they degrade into plain geometry and can no longer be rebuilt parametrically.

---

## 4. Debugging

### 4.1 Look at the load log first

`wirebonder_load.log` is the first place to look when asking "was the addon loaded at all". It records the directory resolution result, whether the icon path exists, the `addWorkbench` state and the effective language. It is written by [`src/InitGui.py`](src/InitGui.py) once registration has finished — one copy in the addon directory and one in `%TEMP%`.

> If **even this log file is missing**, `InitGui.py` raised before it could write the log. A last-resort log `%TEMP%\wirebonder_boot.log` (with the full traceback) is written in that case, and FreeCAD's own start-up is not interrupted — by design: a broken addon must never take FreeCAD down with it.

To obtain FreeCAD's own start-up log, launch it with `--log-file`:

```bat
FreeCAD.exe --log-file "%TEMP%\fc.log"
```

Search the log for `WireBonder`: `Initializing ...\Mod\WireBonder\.\... done` means it was loaded; a `Traceback` or `Err: During initialization the error ...` means the addon raised.

### 4.2 A one-shot self-check snippet

Paste the following into the Python console to verify the installation in one go:

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

### 4.3 Two traps you must know about

**① The `globals` / `locals` trap under `exec`.**
FreeCAD executes `InitGui.py` through `exec(code, globals, locals)`, and the `globals` and `locals` it passes are **not the same dictionary**: the namespace has **no `__file__`**, and **a top-level function that references a module-level variable raises `NameError`** (module-level assignments only land in `locals`, whereas name lookup inside functions uses `globals`). This makes the addon **fail silently** — the directory is fine, no dialog appears, the workbench simply never shows up.
This addon therefore keeps **all of its logic inside a single function** and uses only local/closure variables; [`src/Init.py`](src/Init.py) likewise keeps nothing but the simplest top-level statements. **Do not introduce top-level functions that depend on module-level state when editing these two files.**

**② Chinese console encoding.**
`cmd.exe` defaults to GBK, so `print`ing Chinese in the console may raise `UnicodeEncodeError: 'gbk' codec can't encode character`. That is a **console problem, not an addon problem**; write the result into a file and read it back, or run `chcp 65001` temporarily.

### 4.4 From symptom to cause

| Symptom | Cause and remedy |
| --- | --- |
| The **Wire Bonding** workbench is missing from the selector | ① wrong directory level: `<Mod>/WireBonder/InitGui.py` must exist, do not add an extra level; ② **`Init.py` is missing** → FreeCAD prints `(Init.py not found)... ignore` and skips the whole directory; ③ installed into the wrong version directory (1.1 uses `v1-1`, 1.0 uses `v1-0`, 0.21 uses `v0.21`); ④ FreeCAD was not restarted |
| Directory and files look right, the workbench still does not appear | Mostly the `exec` namespace trap of 4.3①; compare `wirebonder_load.log` against the `Traceback` to locate it |
| The command is greyed out | **Exactly two faces** must be selected. With an edge, a vertex or a whole object (no sub-element) selected, the command disables itself and reports how many faces it recognised |
| `TypeError: int() argument must be ... not 'StandardButton'` when the panel opens | In PySide6 (Qt6) the enums are `enum.Flag`, so `int(QDialogButtonBox.Ok \| Cancel)` cannot be converted directly — you must take `.value` (fixed in 0.1.0; upgrade and restart) |
| An icon shows as a blank square | Make sure the three files `WireBonder/resources/icons/*.svg` exist; you can print `Gui.listWorkbenches()["WireBonderWorkbench"].Icon` to check the path; the `<classname>` in `package.xml` must match the class name in `InitGui.py` |
| `import WireBonder` fails in the console | `sys.path` must point at the **addon root** (the level that contains the `WireBonder/` package), not at the package directory itself |
| Changing a panel parameter has no effect | Trigger a recompute: `Ctrl` + `R`, or run `FreeCAD.ActiveDocument.recompute()` |
| The UI language is wrong | The addon follows FreeCAD's language setting: a Chinese environment shows Chinese, any other language (English included) shows English. Since v0.3.0 switching the language **needs no restart** (change it in **Edit ▸ Preferences ▸ General ▸ Language** and it takes effect immediately); if it is still wrong, look at the `language = zh` / `language switched zh -> en` lines in `wirebonder_load.log` |
| `Link(s) to object(s) ... go out of the allowed scope` | The selected faces sit inside a `PartDesign::Body`. This is a **warning, not an error**, and the geometry is correct; to avoid it entirely, model the pads with the Part workbench instead |
| The gold wire is invisible | 20 µm is practically invisible at a scale of tens of millimetres. By default only the centreline (a thin gold line) is generated for illustration; tick "Create wire solid" to get a real solid |
| Building the solid takes very long | The OCCT sweep of a thin diameter over a long path is expensive (measured: 20 µm × 100 mm takes about a minute). Determine the routing with the centreline first and generate the solid last |

> For anything about **geometry / parameter semantics** (angle reference, the meaning of the control points, apex overshoot, ball size, …) see [`src/README-en.md`](src/README-en.md); a more detailed troubleshooting record lives in section 4 of [`context/agent-guide.md`](context/agent-guide.md).

---

## 5. Dynamic loading

The addon code is loaded **when FreeCAD starts**, so by default you have to restart after editing the source. During development you can avoid the restart cycle in either of the following ways.

### 5.1 Loading into the current session (no restart, nothing written to the Mod directory)

Run this in the Python console:

```python
import os, sys
addon = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder")
if addon not in sys.path:
    sys.path.append(addon)

import WireBonder.commands          # registers the two commands
import FreeCADGui as Gui
Gui.activateWorkbench("WireBonderWorkbench")
```

The workbench and toolbar appear in the current session immediately. You can also point `addon` at the repository's [`src/`](src) directory and try the addon straight from the source tree, without installing it first.

> This lasts **for the current session only**; the addon still needs a proper installation to be loaded automatically next time.

### 5.2 Hot-reloading the installed modules

Edit the source → sync it to the Mod directory (the manual copy of option A, or overwrite it with your own script) → then reload in the console:

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

Notes:

- **Reload order**: `core` / `settings` / `i18n` are the lower layers and `features` / `taskpanel` / `commands` depend on them, so reload in the order shown above;
- **Registering modules** (`commands`, `InitGui`): after a reload the menu/toolbar may still point at the old objects. `Gui.addWorkbench` does **not** overwrite a workbench of the same name, so the easiest way to make new buttons effective is to **re-execute [`src/InitGui.py`](src/InitGui.py)** — its internal `register_workbench()` already wraps the full "remove if present, otherwise add" flow (runtime language switching reuses the very same routine):
  ```python
  import os, FreeCAD
  init_gui = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder", "InitGui.py")
  exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"))
  ```
  Re-executing overwrites `wirebonder_load.log`, which lets you confirm that this registration also logged `addWorkbench OK`;
- **`__pycache__` gets in the way**: when you suspect stale bytecode, delete every `__pycache__` under the installed directory and try again;
- **Existing objects keep the old code**: `reload` only affects objects created **afterwards**; a `WireBond` already present in a document walks the new implementation on its next `recompute()` (its class's `execute()` was updated along with the module reload, but if the property structure changed you have to recreate the object);
- **`Init.py` / `InitGui.py` cannot be fully reproduced by a reload** — restart FreeCAD for changes to these two files.

---

## 6. File structure

### 6.1 Repository layout

```text
wire-bonder/
├── README.md                      # this file: overview / requirements / installation / debugging / dynamic loading / file structure
├── README-en.md                   # English translation of this file
├── context/
│   └── agent-guide.md             # handover guide: key decisions, pitfalls
├── data/                          # reference images and generated comparison figures
├── docs/
│   ├── freecad-wirebonder-prd.md  # design document (requirements / algorithm / data model / revision log)
│   ├── parameters.md              # detailed description of every parameter
│   ├── spline-ctrl-points.md      # specification of the loop control points
│   └── images/
├── scripts/                       # standalone Python tools, none of which need FreeCAD
│   ├── wirebond_sketch.py         # draws the control-point sketch (Chinese/English, see --help)
│   └── draw_two_squares.py
└── src/                           # ★ addon source, copied wholesale into the Mod directory on install
    ├── Init.py
    ├── InitGui.py
    ├── package.xml
    ├── README.md / README-en.md   # addon function and geometry docs (Chinese / English)
    ├── wirebond-sketch-zh.png     # sketch (Chinese annotations)
    ├── wirebond-sketch-en.png     # sketch (English annotations)
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

### 6.2 The installed addon directory

```text
<Mod>/
└── WireBonder/                    # addon root (naming it WireBonder is recommended)
    ├── Init.py                    # required
    ├── InitGui.py                 # required
    ├── package.xml
    ├── README.md / README-en.md
    ├── wirebonder_load.log        # written automatically after the first load, for troubleshooting
    └── WireBonder/                # the Python package
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

### 6.3 Responsibilities of each file

| File | Purpose |
| --- | --- |
| [`src/Init.py`](src/Init.py) | The non-GUI loading entry point; it is also the "this is an addon directory" marker (FreeCAD skips the directory without it) and appends the addon root to `sys.path` so that `import WireBonder` works straight from the console |
| [`src/InitGui.py`](src/InitGui.py) | Registers the `WireBonderWorkbench` workbench, its toolbar and its menu; the logic lives entirely inside a single function (to dodge the `globals`/`locals` trap under `exec`) and the loading process is written to `wirebonder_load.log` |
| [`src/package.xml`](src/package.xml) | Addon Manager metadata (name, version, icon, workbench class name, `subdirectory`) |
| [`src/WireBonder/core.py`](src/WireBonder/core.py) | The geometry core, **free of GUI dependencies**: centroids/normals, the loop frame, the loop control points, the spline, the sweep, the bond balls |
| [`src/WireBonder/features.py`](src/WireBonder/features.py) | The parametric objects `WireBond` / `WireBondPlane` and their display styles (gold wire, semi-transparent helper plane) |
| [`src/WireBonder/taskpanel.py`](src/WireBonder/taskpanel.py) | The parameter panel (PySide2 / PySide6 compatible, using FreeCAD's native `Gui::QuantitySpinBox`) |
| [`src/WireBonder/commands.py`](src/WireBonder/commands.py) | The FreeCAD commands, selection validation and degenerate-case pre-checks |
| [`src/WireBonder/settings.py`](src/WireBonder/settings.py) | Persistence of the panel parameters (FreeCAD user parameters) |
| [`src/WireBonder/i18n.py`](src/WireBonder/i18n.py) | The Chinese/English catalogue (the English original is the msgid) |
| [`src/WireBonder/language_monitor.py`](src/WireBonder/language_monitor.py) | Watches for runtime language changes, so no restart is needed |
| [`src/WireBonder/resources/icons/*.svg`](src/WireBonder/resources/icons) | The icons of the workbench and of the two commands |
| [`scripts/wirebond_sketch.py`](scripts/wirebond_sketch.py) | The offline sketch script (Chinese/English/both, `-l` selects the language, `-o` sets the output) |

---

## 7. Development conventions

- After editing the source you **must re-sync** it to the Mod directory and restart FreeCAD, or hot-reload as described in section 5 — otherwise you keep looking at the old code;
- Quote every user-visible string as `_("English text")`; the catalogue is [`src/WireBonder/i18n.py`](src/WireBonder/i18n.py) and the procedure for adding a language is in the "Multi-language support" section of [`src/README-en.md`](src/README-en.md);
- Bump the version in **both** `__version__` in [`src/WireBonder/__init__.py`](src/WireBonder/__init__.py) and `<version>` in [`src/package.xml`](src/package.xml);
- When editing [`src/Init.py`](src/Init.py) / [`src/InitGui.py`](src/InitGui.py), respect the "no top-level function that depends on module-level state" constraint.

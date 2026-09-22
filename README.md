# WireBonder Addon — Installation Guide

A wire bonding (gold wire) helper addon for FreeCAD: **select two faces → the bisector plane is built automatically → a gold wire is created along the line connecting the two centroids**, with a configurable wire diameter and clearance.

- Addon source: [`src/`](src/README.md)
- Design document: [`docs/freecad-wirebonder-prd.md`](docs/freecad-wirebonder-prd.md)
- Addon entry point: [`src/InitGui.py`](src/InitGui.py)
- Non-GUI entry point: [`src/Init.py`](src/Init.py)
- Geometry core: [`src/WireBonder/core.py`](src/WireBonder/core.py)
- Chinese version of this file: [`README-cn.md`](README-cn.md)

---

## 1. Prerequisites

| Item | Requirement | Verified on this machine |
| --- | --- | --- |
| FreeCAD | 1.0 / 1.1 (1.1 recommended) | 1.1.3 |
| Python | 3.8+ (bundled with FreeCAD) | 3.11.14 |
| Qt binding | PySide6 (FreeCAD 1.x ships a `PySide` compatibility layer) | PySide6 6.8.3 |

The addon only uses `FreeCAD`, `Part`, `FreeCADGui` and `PySide`, all of which ship with FreeCAD — **no additional pip dependency is required**.

---

## 2. Step 1: Locate the Mod (addon) directory

The FreeCAD user-level addon directory **contains a version number**, and the name differs between releases (`v1-1`, `v1-0`, `v0.21`, …). The most reliable way is to ask FreeCAD itself.

Open FreeCAD, go to **View ▸ Panels ▸ Python console** and run:

```python
import os
print(os.path.join(FreeCAD.getUserAppDataDir(), "Mod"))
```

The output is the directory where the addon must be placed, for example on this machine:

```sh
C:\Users\Edison\AppData\Roaming\FreeCAD\v1-1\Mod
```

Default locations per platform (for reference):

| Platform | Mod directory |
| --- | --- |
| Windows | `%APPDATA%\FreeCAD\v1-1\Mod\` |
| Linux | `~/.local/share/FreeCAD/v1-1/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |

> Simply create the directory manually if it does not exist.
>
> ⚠ **The addon directory must contain both `Init.py` and `InitGui.py`**: when FreeCAD starts it walks every subdirectory of Mod and only loads those containing `Init.py` as addons. A directory without `Init.py` is reported in the startup log as
> `Initializing ...(Init.py not found)... ignore` and skipped entirely (verified by experiment).

---

## 3. Step 2: Install

### Option A: manual copy (recommended, simplest)

Copy the [`src/`](src/README.md) directory of this project into the Mod directory and **rename it to `WireBonder`** (`src` is the source directory name of this project; after installation the addon directory is ideally called `WireBonder`).

#### Windows (run from the project root)

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

The resulting directory structure should be:

```text
<Mod>/
└── WireBonder/                 <- addon root (ideally named WireBonder)
    ├── Init.py                 <- required, without it FreeCAD skips the whole directory
    ├── InitGui.py              <- required, the workbench is registered here
    ├── package.xml             <- Addon Manager metadata (workbench class name / icon)
    ├── README.md
    ├── wirebonder_load.log     <- generated after the first load, for troubleshooting
    └── WireBonder/             <- Python package
        ├── __init__.py
        ├── core.py
        ├── features.py
        ├── taskpanel.py
        ├── commands.py
        └── resources/icons/*.svg
```

### Option B: Addon Manager (from a zip archive)

1. Pack the addon root into a zip (the zip must contain `InitGui.py` and `package.xml` **directly**, without an extra enclosing folder):

   ```bat
   :: Windows
   powershell -Command "Compress-Archive -Path .\src\* -DestinationPath .\WireBonder.zip -Force"
   ```

   ```bash
   # Linux / macOS
   (cd src && zip -r ../WireBonder.zip .)
   ```

2. In FreeCAD open **Tools ▸ Addon manager**, choose **Install from file…** in the top-right drop-down and select `WireBonder.zip`.
3. Restart FreeCAD when prompted.

### Option C: try it without restarting (temporary load in the current session)

If you do not want to restart FreeCAD, run this in the Python console:

```python
import os, sys
addon = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder")
if addon not in sys.path:
    sys.path.append(addon)

import WireBonder.commands          # registers the two commands
import FreeCADGui as Gui
Gui.activateWorkbench("WireBonderWorkbench")
```

The workbench and toolbar appear immediately in the current session; **a proper installation as described above is still required for the next startup**.

### Option D: scripted install (bash / msys2 / Linux / macOS)

The [`install.sh`](install.sh) script in the project root locates the Mod directory and performs the installation:

```bash
./install.sh
```

The script is just two commands; the important part is **`cp -rfT`**:

```bash
DEST="$(ls -d "${APPDATA:-$HOME}"/FreeCAD/*/Mod | head -n 1)/WireBonder"
mkdir -p "$DEST"
cp -rfT src "$DEST"
```

**`-T` (GNU `--no-target-directory`) is the key**: it makes `cp` treat DEST as an ordinary
directory, so the **contents** of `src` are copied into `WireBonder` instead of creating
`WireBonder/src` when the destination already exists. Without `-T`, every run nests one more level.

The same behaviour without `-T`: append `/.` to the source path.

```bash
cp -rf src/. "$DEST/"      # equivalent to cp -rfT src "$DEST"
```

> Note: `cp -T` is a GNU coreutils extension available on Linux / msys2 / cygwin;
> BSD/macOS `cp` has no `-T`, so use the `src/.` form there.

> Note: this loads the code from the installed directory on `sys.path`; remember to re-sync the installed directory after editing the sources.

---

## 4. Step 3: Verify the installation

After restarting FreeCAD, check the following:

1. **Workbench selector** shows **Wire Bonding** (tooltip: builds the bisector plane of two faces and creates a wire loop).
2. **Python console** — the following check should list two commands:

   ```python
   import FreeCADGui as Gui
   print([c for c in Gui.listCommands() if "WireBonder" in c])
   # ['WireBonder_CreatePlane', 'WireBonder_CreateWireBond']
   ```

3. **Toolbar** below the menu bar: after selecting the `Wire Bonding` workbench you should see the two buttons `Create Wire Bond` and `Create Bisector Plane` (gold arc icon / green plane icon).

4. **Check the addon load log** (regenerated on every FreeCAD start):

   ```text
   <Mod>\WireBonder\wirebonder_load.log      (Windows)
   %TEMP%\wirebonder_load.log               (a copy on every platform)
   ```

   A successful load looks like:

   ```log
   [2026-09-21 13:14:54] no __file__ in this namespace (NameError(...)), fall back to sys.path
   [2026-09-21 13:14:54] addon_dir  = C:\Users\Edison\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder
   [2026-09-21 13:14:54] package_dir= ...\Mod\WireBonder\WireBonder
   [2026-09-21 13:14:54] icon_dir   = ...\resources\icons (exists: True)
   [2026-09-21 13:14:54] language   = zh
   [2026-09-21 13:14:54] addWorkbench OK
   ```

   - The first line means FreeCAD executes `InitGui.py` through `exec` (no `__file__`), and the addon automatically falls back to `sys.path` — this is **normal**;
   - `addWorkbench OK` means registration succeeded;
   - If you see `addWorkbench FAILED`, or the file does not exist at all, continue with the next section.

Verified on this machine: the workbench `WireBonderWorkbench` registered successfully, `MenuText = "Wire Bonding"`, the icon path resolves correctly, both commands register once the workbench is activated, the toolbar group `Wire Bonding` contains the two commands, and the load log ends with `addWorkbench OK`.

---

## 5. First use

1. Select **two faces**: hold `Ctrl` in the 3D view and click two faces (they may belong to the same body or to two different objects);
2. Click **Wire Bonding ▸ Create Wire Bond**;
3. Fill in the parameters in the panel:

   | Parameter | Default | Description |
   | --- | --- | --- |
   | Wire diameter | 20 µm | Sweep section diameter |
   | Clearance | 500 µm | Height of the loop peak **above the centroid line** (entered in µm) |
   | Wire plane rotation | 0° | Rotation of the wire plane about the centroid line (−180°~180°); 0° is coincident with the bisector plane |
   | Peak position ratio | 0.42 | Loop peak position as a ratio of the centroid distance |
   | Rise height ratio | 0.60 | Height ratio of the steep rise point near the start |
   | Fall height ratio | 0.20 | Controls the landing attitude |
   | Bond ball diameter | 50 µm | Diameter of the bond ball at each bond point |
   | Create the gold wire solid | unchecked | When checked, creates a solid with the real diameter (slower) |
   | Also show the centreline | checked | Helps to see the wire path at small diameters |
   | Create bond balls | checked | Creates a ball at each centroid |
   | Create the bisector helper plane | unchecked | Bisector helper plane (construction reference, hidden after creation); **off by default** to keep the object count low |

4. Click **OK** to create `WireBond` (gold wire + bond balls, gold coloured); the bisector plane is created as a **helper plane** and hidden automatically;
5. Afterwards you can edit `WireDiameter`, `Clearance`, `PeakRatio`, `MakeBalls`, `BallDiameter`, and so on in the **property editor** at any time — the geometry rebuilds automatically.

> If the selected faces belong to a `PartDesign::Body`, the Report view shows the
> `Link(s) to object(s) ... go out of the allowed scope` message: this is a **warning** and the geometry is unaffected.

---

## 6. Upgrade and uninstall

**Upgrade**: overwrite with the same directory (run the Option A copy command again), then **restart FreeCAD** (addon code is loaded at startup, so the new version only takes effect after a restart).

```bat
xcopy /E /I /Y src "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

> If the behaviour does not change after overwriting, delete the `__pycache__` inside the installed directory and restart.

**Uninstall**: delete the addon directory under Mod and restart FreeCAD.

```bat
rmdir /s /q "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

```bash
rm -rf ~/.local/share/FreeCAD/v1-1/Mod/WireBonder
```

> Uninstalling only affects the addon itself; gold wire objects created with it live inside their own `.FCStd` documents and are unaffected (they simply become plain geometry and can no longer be rebuilt parametrically).

---

## 7. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| **Wire Bonding** is missing from the workbench selector | ① wrong directory name/layout: `<Mod>/WireBonder/InitGui.py` must exist, without an extra enclosing folder; ② **`Init.py` is missing** — FreeCAD prints `(Init.py not found)... ignore` and skips the whole directory; ③ the addon was placed in the wrong version directory (1.1 is `v1-1`, 1.0 is `v1-0`, 0.21 is `v0.21`); ④ FreeCAD was not restarted |
| The directory and files look fine but the workbench still does not appear | FreeCAD executes `InitGui.py` with **`exec(code, globals, locals)`**, and the `globals` and `locals` it passes are **not the same dictionary**: the namespace has **no `__file__`**, and **a top-level function that references a module-level variable raises `NameError`** (module-level assignments only land in `locals`, while name lookup in functions uses `globals`). The addon therefore fails *silently* — correct directory, no dialog, no workbench. This addon avoids it by keeping all logic inside **a single function** and using only local/closure variables |
| How to tell whether the addon was loaded at all | ① open `<Mod>\WireBonder\wirebonder_load.log` (written on every startup, containing the resolved directory and the `addWorkbench` status; a copy also goes to `%TEMP%`); ② start with `FreeCAD.exe --log-file "%TEMP%\fc.log"` and search for `WireBonder`: `Initializing ...\Mod\WireBonder\.\... done` means it was loaded, while `Traceback` / `Err: During initialization the error ...` means the addon raised |
| `TypeError: int() argument must be ... not 'StandardButton'` when the panel opens | PySide6 (Qt6) enums are `enum.Flag`, so `int(QDialogButtonBox.Ok \| Cancel)` cannot be converted directly and `.value` must be used. Fixed in 0.1.0; upgrade the addon and restart |
| `Link(s) to object(s) ... go out of the allowed scope` on creation | The selected faces lie inside a `PartDesign::Body`. This is a **warning, not an error**, and the geometry is still correct; both the panel and the Report view explain it. To avoid it entirely, model the pads with the Part workbench (putting the objects into an `App::Part` at the same level as the Body does *not* help, because the Body is the inner scope) |
| `ViewProviderTransformed: Only additive and subtractive features can be transformed` | The transform tool was applied to a PartDesign **pattern feature** (`LinearPattern` / `LinearPattern001`, …). These "multi-transform features" cannot be transformed: edit their `Length` / `Occurrences` / `Direction` instead, or select the `Body` and change its `Placement`. **This error is unrelated to the addon** |
| The command is greyed out | Exactly **two faces** must be selected. If an edge, a point or a whole object is selected (no sub-elements), the command disables itself and reports how many faces were detected |
| Message "the two face normals are 180 degrees apart" | The two faces point in opposite directions, so no bisector exists. Pick two faces with a **consistent orientation** (for example the top faces of two pads) |
| Message "the centroid line is parallel to the normal bisector" | The plane is not unique in that configuration (a degenerate case); pick another pair of faces or change the orientation of one of them |
| The gold wire is invisible | 20 µm is practically invisible at a scale of tens of millimeters, which is expected. Only the centreline (a thin gold line) is generated by default; check "Create the gold wire solid" for a real solid |
| The bisector plane object cannot be found | It is a **helper plane** and the one created by `Create Wire Bond` is hidden automatically (the object remains in the tree — tick it to show). Use the `Create Bisector Plane` command if you want a visible plane directly |
| The wire is drawn outside the model and the start point looks wrong | Before v0.1.2 the **assembly coordinate system** was not handled: when the faces came from a part inside an `App::Part`, the centroid was computed in local coordinates (measured deviations of several millimeters). Fixed (`core.global_face()` compensates the parent transform); upgrade, restart and regenerate. The panel now shows the **global** centroids and the **centroid distance L** for verification |
| The panel warns "the clearance is larger than the centroid distance" | When two pads are very close (for example L = 0.393 mm) and the clearance is 500 µm, the loop looks exaggerated. Reduce the clearance, or double-check that the correct faces were selected |
| Bond balls are too large / too small | Adjust "Bond ball diameter" in the panel or the `BallDiameter` property (default 50 µm); uncheck "Create bond balls" or turn off `MakeBalls` when not needed |
| Creating the solid takes a very long time | OCCT sweeping is expensive for thin diameters over long paths (measured: about 1 minute for 20 µm × 100 mm). Establish the path with the centreline first and generate the solid last, or temporarily increase the diameter |
| Icons show as empty squares | Make sure all three `WireBonder/resources/icons/*.svg` files exist; if needed print `Gui.listWorkbenches()["WireBonderWorkbench"].Icon` in the console to check the path. The `<classname>` in `package.xml` must also match the class name in `InitGui.py` |
| Changing a parameter has no effect | Trigger a recompute with `Ctrl` + `R`, or run `FreeCAD.ActiveDocument.recompute()` in the Python console |
| `import WireBonder` fails in the console | `sys.path` must point to the **addon root** (the directory containing the `WireBonder/` package), not to the package directory itself |
| The UI language is not Chinese (or not English) | The addon **follows the FreeCAD language setting**: Chinese shows Chinese, every other language (including English) shows English. Since v0.3.0 **switching the language needs no restart** — change it under **Edit ▸ Preferences ▸ General ▸ Language** and the workbench name, toolbar/menu buttons and the parameter panel follow immediately. If it still does not, check `language = zh`/`en` and `language switched zh -> en` in `wirebonder_load.log`. Objects created by earlier versions keep the property descriptions from their creation time, which is expected |

---

## 8. Appendix: installation check snippet

Paste this into the Python console to verify the installation in one go:

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

Expected output (measured on this machine):

```log
addon dir      : C:\Users\<user>\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder True
Init.py        : True
InitGui.py     : True
package.xml    : True
core.py        : OK
defaults       : clearance = 0.5 mm | ball dia = 0.05 mm
workbench      : registered
icon exists    : True
commands       : ['WireBonder_CreatePlane', 'WireBonder_CreateWireBond']
load log       : ...\Mod\WireBonder\wirebonder_load.log True
[2026-09-21 13:14:54] ... addWorkbench OK
```

---

## 9. Addon file list

| File | Purpose |
| --- | --- |
| `Init.py` | Non-GUI entry point; also the marker that makes the directory an addon (without it FreeCAD skips it), and adds the addon root to `sys.path` |
| `InitGui.py` | Registers the `WireBonderWorkbench` workbench, toolbar and menu; all logic lives in a single function (avoiding the FreeCAD `exec` `globals`/`locals` trap) and the load process is written to `wirebonder_load.log` |
| `package.xml` | Addon Manager metadata (name, version, icon, workbench class name, `subdirectory`) |
| `WireBonder/core.py` | Geometry core (no GUI dependency): centroids/normals, bisector plane frame, wire loop control points, spline, sweep, bond balls |
| `WireBonder/features.py` | Parametric objects `WireBond` / `WireBondPlane` and their display styles (gold wire, semi-transparent helper plane) |
| `WireBonder/taskpanel.py` | Parameter input panel (PySide2 / PySide6 compatible) |
| `WireBonder/commands.py` | FreeCAD commands, selection validation and degenerate-case pre-check |
| `WireBonder/i18n.py` | Multi-language support (Chinese / English, follows the FreeCAD language setting) |
| `WireBonder/resources/icons/*.svg` | Workbench and command icons |
| `README.md` | Addon features, geometry construction rules, parameters, scripting and troubleshooting |

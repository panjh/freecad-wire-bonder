# WireBonder — Wire Bonding (Gold Wire) Helper Addon for FreeCAD

Select any **two planar faces**; the addon builds a *bisector plane* between them, draws a **wire loop** connecting the two face centroids inside that plane, and finally sweeps a circle of the configured **wire diameter** along it to create a solid (optionally with two bond balls).

The wire diameter, clearance, loop peak position and all other settings are **parametric properties** — geometry rebuilds automatically after any change.

| Related document | Location |
| --- | --- |
| **Parameter reference** (what every parameter does) | [`../docs/parameters.md`](../docs/parameters.md) |
| Product design document (PRD) | [`../docs/freecad-wirebonder-prd.md`](../docs/freecad-wirebonder-prd.md) |
| Installation guide | [`../README.md`](../README.md) |
| Chinese version of this file | [`README-cn.md`](README-cn.md) |
| Addon source | this directory [`src/`](.) |

> Version 0.2.0 ｜ verified on **FreeCAD 1.1.3 + Python 3.11.14 + PySide6 6.8.3**.
>
> **v0.2.0**: added **multi-language support** — the UI follows the FreeCAD language setting:
> Chinese is shown in Chinese, **every other language (including English) is shown in English**.
> New module [`WireBonder/i18n.py`](WireBonder/i18n.py).
>
> **v0.1.3**: added the **wire plane rotation** `PlaneRotation` (default `0°`, coincident with the
> bisector plane) — the plane containing the wire can be rotated about the centroid line by any angle.
>
> **v0.1.2 (important fix)**: corrected the assembly coordinate system — when the faces come from
> parts inside an `App::Part` container, the parent transform is now compensated properly (previously
> the centroid was computed in local coordinates and the wire was drawn outside the model). The panel
> now shows **global** centroids plus the **centroid distance L** and warns when the clearance exceeds it.
>
> v0.1.1: default clearance changed to **500 µm**, default bond ball diameter to **50 µm**; the bisector
> helper plane is **no longer created by default**; added the PartDesign Body scope warning (orange panel
> note + Report view message).

---

## 1. Geometry Construction Rules

Given two selected faces F1 and F2:

1. Take the **centroids** C1, C2 and the connecting direction `d = normalize(C2 - C1)`;
2. Take the **normals** n1, n2, first align them to the same hemisphere (flip n2 when the angle exceeds 90°), then take the **bisector direction** `b = normalize(n1 + n2)`;
3. The target plane P is spanned by `d` and `b`, and it passes through both C1 and C2;
4. Build a local frame inside P: the x axis along `d`, the y axis as the orthogonal component of `b` within P (Gram-Schmidt), the z axis as the plane normal `x × y`;
   if a **wire plane rotation** θ is set (default 0°), the y and z axes are **rotated by θ about the x axis (the connecting line)** — i.e. the wire plane tilts about the line, and 0° is exactly coincident with the bisector plane;
5. Generate the wire loop inside P: it leaves C1 with a steep rise → loop peak → gentle descent back to C2;
6. Sweep a circle of diameter `WireDiameter` along the curve to obtain the gold wire solid; optionally add a spherical bond ball at each centroid.

Two typical faces (two horizontal pads, both normals pointing +Z) produce a **vertical bisector plane**; two tilted pads produce a plane tilted according to the bisector of their normals.

### Wire Loop Control Points

In local coordinates `(u, v)` (`L` = centroid distance, `H` = clearance, `p` = peak position ratio):

| u | v | Meaning |
| --- | --- | --- |
| `0` | `0` | First bond point (C1) |
| `0.12·p·L` | `rise·H` | Steep rise after leaving the pad |
| `0.50·p·L` | `0.92·H` | Rising section |
| `p·L` | `H` | **Loop peak** |
| `p·L + 0.38·tail` | `0.86·H` | Descending section |
| `p·L + 0.78·tail` | `fall·H` | Landing attitude |
| `L` | `0` | Second bond point (C2) |

Seven control points are used in total - the peak plus three on each side (`tail = L - p·L`).

The control points are interpolated by `Part.BSplineCurve.interpolate()` into a smooth spline, so the curve **passes exactly through both centroids** and **lies entirely inside the bisector plane** (measured endpoint error < 1e-7 mm). Placing the landing point at `0.78·tail` keeps the final segment long enough that the spline never bulges past the second bond point.

## 2. Installation

Copy the `src` directory of this project into the FreeCAD Mod directory and rename it to `WireBonder`:

| Platform | Mod directory |
| --- | --- |
| Windows | `%APPDATA%\FreeCAD\v1-1\Mod\` |
| Linux | `~/.local/share/FreeCAD/v1-1/Mod/` |
| macOS | `~/Library/Application Support/FreeCAD/v1-1/Mod/` |

> The directory name contains a version (`v1-1` / `v1-0` / `v0.21`). The most reliable way to find the
> real path is to run `os.path.join(FreeCAD.getUserAppDataDir(), "Mod")` in the FreeCAD Python console.

```bat
:: Windows example
xcopy /E /I /Y src "%APPDATA%\FreeCAD\v1-1\Mod\WireBonder"
```

```bash
# Linux / macOS
cp -r src ~/.local/share/FreeCAD/v1-1/Mod/WireBonder
```

After restarting FreeCAD, **Wire Bonding** appears in the workbench selector.

> ⚠ The addon directory **must contain both `Init.py` and `InitGui.py`**: FreeCAD only treats a
> subdirectory as an addon when `Init.py` is present, otherwise it prints
> `(Init.py not found)... ignore` in the startup log and skips it.

You can also install the `package.xml`-based zip through the Addon Manager's "Install from file" dialog.

**Trying it without restarting** (temporarily load it in the current session):

```python
import os, sys
addon = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder")
if addon not in sys.path:
    sys.path.append(addon)
import WireBonder.commands                      # registers both commands
import FreeCADGui as Gui
Gui.activateWorkbench("WireBonderWorkbench")
```

## 3. Usage

1. Select **two faces** in the 3D view (hold `Ctrl` for multi-select; they may belong to the same object or to two different objects);
2. Click **Wire Bonding ▸ Create Wire Bond** in the toolbar (or the identical menu entry);
3. Set the parameters in the dialog and press **OK**;
4. A `WireBond` object is created (gold wire + bond balls, gold colored); when enabled, a `WireBondPlane`
   **bisector helper plane** is created as well (semi-transparent green, hidden automatically after
   creation — show it from the tree when needed).

### Panel Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| Wire Diameter | 20 µm | Sweep section diameter, i.e. the gold wire diameter |
| Clearance | 500 µm | Height of the flat top **above the centroid line** |
| Wire Plane Rotation | 0° | Rotation of the wire plane about the centroid line (−180°~180°); **0° is coincident with the bisector plane** |
| Peak Position Ratio | 0.42 | Position of the flat top as a ratio of the centroid distance (0.05–0.95) |
| Rise Angle | 75° | Direction the wire leaves the first pad, measured from the pad-to-pad line |
| Fall Angle | 20° | Direction the wire reaches the second pad, measured from the pad-to-pad line |
| Bond Bump at C1 | Sphere | Shape at the first bond point: **none / sphere / frustum** |
| Bond Bump at C2 | Sphere | Shape at the second bond point; may differ from C1 (e.g. ball on the chip, frustum on the substrate) |
| Lead Distance | 30 µm | Distance from each pad to its control point B / D, measured along the rise / fall ray |
| Ball Diameter | 50 µm | Sphere: the ball diameter (about 2.5× the wire diameter). Frustum: the bump height |
| Frustum Top Diameter | 50 µm | Frustum: diameter of the end away from the pad (shown for frustum only) |
| Frustum Bottom Diameter | 50 µm | Frustum: diameter of the end on the pad (shown for frustum only) |
| Create the gold wire solid | No | Produces a solid with the real diameter; sweeping is slow for tiny diameters |
| Also show the centreline | Yes | Also visible when only the centreline is generated, handy for small diameters |
| Create bond balls | Yes | Creates a ball at each centroid; the diameter comes from "Bond Ball Diameter" |
| Create the bisector helper plane | No | Additionally creates the bisector plane (construction reference, hidden afterwards); **off by default** to keep the object count low |

> **The panel remembers the settings used last time**: pressing OK stores the current values in the
> FreeCAD user parameters (`User parameter:BaseApp/Preferences/Mod/WireBonder`) and the next panel
> opens with them - wire diameter, clearance, wire plane rotation, all ratios, the bond ball diameter
> and every checkbox. Use the **Restore Defaults** button at the bottom of the panel to go back to the
> built-in values (it also clears the stored settings), or delete them manually under
> **Tools ▸ Edit parameters ▸ BaseApp ▸ Preferences ▸ Mod ▸ WireBonder**.

### Parameter input fields

Every numeric field is a **`Gui::QuantitySpinBox`** - the same widget the FreeCAD property
editor uses - so it brings three conveniences with it:

- **free unit switching**: the unit is part of the value, so you can type `0.02 mm`, `20 um`
  or `1 thou` and the display follows (the context menu also offers conversions). The length
  fields (Wire Diameter, Clearance, Bond Ball Diameter) accept any length unit; the angle
  field (Wire Plane Rotation) accepts `deg` / `rad`;
- **expressions**: evaluated on commit, e.g. `10*2`, `0.25*2`, `5um*4`, or a reference to a
  `Spreadsheet` cell;
- **scrolling over a field does not change its value** (the native behaviour would): the wheel
  event is handed to the panel instead, so the panel still scrolls under the cursor.

The dimensionless ratio fields (Peak Position Ratio, Rise Height Ratio, Fall Height Ratio)
accept expressions as well.

### Panel layout

- **Scrolls automatically**: when the content is taller than the available space a vertical scrollbar
  appears, so no control is ever cut off. The content width adapts to the panel and no horizontal
  scrollbar is needed.
- **Collapsible sections**: click a section title (**Selected Faces** / **Wire Parameters** /
  **Output Options**) to collapse or expand it - **▾** means expanded, **▸** means collapsed. Handy on
  small screens. The collapse state is remembered (saved immediately, no OK required; the
  **Restore Defaults** button does not reset it).

> A 20 µm gold wire is practically invisible at assembly scale (tens of millimeters), so only the
> **centreline** is generated by default; enable "Create the gold wire solid" when a real solid is needed.
>
> If the selected faces lie inside a `PartDesign::Body`, the Report view shows the
> `Link(s) to object(s) ... go out of the allowed scope` **warning** (not an error) and the geometry is
> unaffected; the panel detects this automatically and shows an orange note at the top, and the command
> prints the same explanation in the Report view.

### Parametric Editing

After creation you can edit `WireDiameter`, `Clearance`, `PlaneRotation`, `PeakRatio`, `RiseAngle`,
`FallAngle`, `LeadDistance`, `MakeSolid`, `ShowCentreline` and `BallDiameter` in the **property editor** —
the geometry rebuilds automatically. You may also change `Face1` / `Face2` to use different faces.

## 4. Scripting / Console Usage

The geometry core does not depend on the GUI and can be called directly:

```python
import sys
sys.path.append(r"C:\Users\<you>\AppData\Roaming\FreeCAD\v1-1\Mod\WireBonder")

import FreeCAD as App
from WireBonder import core

doc = App.ActiveDocument
face1 = doc.getObject("Pad1").Shape.Faces[1]   # any face
face2 = doc.getObject("Pad2").Shape.Faces[1]

result = core.compute_from_faces(
    face1, face2,
    wire_diameter=0.02,   # 20 µm
    clearance=0.5,        # clearance 500 µm
    peak_ratio=0.42,      # loop peak position ratio
    rise_ratio=0.60,      # steep rise ratio
    fall_ratio=0.20,      # landing height ratio
    make_solid=False,     # compute the centreline only
        ball_diameter=0.05,   # bond ball diameter 50 µm
)
print(result["frame"].length)      # centroid distance
print(result["centre_line"])       # centreline Wire
print(result["solid"])             # wire solid (when make_solid=True)
print(result["balls"])             # the two bond ball solids
print(result["plane"])             # bisector plane Face (for the helper plane)
```

You can also create the parametric object directly with `WireBonder.features.WireBondFeature`:

```python
from WireBonder import features

obj = doc.addObject("Part::FeaturePython", "WireBond")
features.WireBondFeature(obj)
features.ViewProviderWireBond(obj.ViewObject)   # gold display style
obj.Face1 = (doc.getObject("Pad1"), "Face6")
obj.Face2 = (doc.getObject("Pad2"), "Face6")
obj.Clearance = "500 um"
obj.WireDiameter = "20 um"
obj.BallDiameter = "50 um"
obj.StartBallMode = "sphere"
obj.EndBallMode = "frustum"
doc.recompute()
```

## 5. Known Limitations

- **Sweeping a thin wire solid is slow**: a 0.02 mm diameter pipe over hundreds of millimeters is heavy for OCCT and takes about one minute in practice; generating the centreline only is almost instantaneous.
- **Degenerate normal cases**: when the two face normals are exactly opposite (180°) no bisector exists and the addon reports it; pick two faces with a consistent orientation instead.
- When the **connecting line is parallel to the bisector** the plane is not unique and the addon also reports it.
- **Clearance definition**: it is the height of the loop peak *relative to the centroid line*, not relative to the component surface; convert manually if a surface-based reference is needed.
- **Scope isolation warning**: when the faces come from a `PartDesign::Body`, creating the object necessarily triggers the `go out of the allowed scope` warning (see §3). This is FreeCAD's scope mechanism and the addon cannot remove it; model the pads with the Part workbench (`Part::Box`, etc.) to avoid it.
- **Assembly coordinate system**: when the faces come from parts inside an `App::Part` container, the addon compensates the parent transform (`getGlobalPlacement()`) so the wire always lands in the global assembly position. If you later **move the parent container** (change the `App::Part` Placement), press `Ctrl` + `R` once to recompute and refresh the geometry.
- **Clearance versus span**: when the clearance exceeds the centroid distance the loop looks exaggerated (the panel shows an orange note); remember the loop height is measured **relative to the centroid line**, not to the component surface.
- **Do not use the transform tool on PartDesign patterns**: `LinearPattern`/`LinearPattern001` are "multi-transform features" and PartDesign only allows transforming additive/subtractive features, so transforming them raises `ViewProviderTransformed: Only additive and subtractive features can be transformed`. To change a pattern, edit its `Length`/`Occurrences`/`Direction`; to move the whole part, select the `Body` and change its `Placement`.
- `WireBondPlane` is a **helper plane**: the one created by `Create Wire Bond` is hidden automatically (show it from the tree when needed); use the `Create Bisector Plane` command if you want a visible bisector plane directly. Its rectangle extends automatically and can be tuned with `Margin` and `WidthFactor`.
- Bond bumps are placed at the two face centroids and their diameter comes from `BallDiameter`; they take part in the parametric rebuild as well — change the diameter or set the matching **Bond Bump** selector to "none".
- The wire solid and the centreline live in the same `Compound`, so they **share a single color** (gold).

## 6. Troubleshooting Addon Loading

1. **FreeCAD startup log**: launch with `FreeCAD.exe --log-file "%TEMP%\fc.log"`. A line such as
   `Init: Initializing ...\Mod\WireBonder\.\... done` means the addon was discovered and executed;
   a `Traceback` / `Err: During initialization the error ...` means the addon raised an exception.
2. **The addon's own log**: `<Mod>\WireBonder\wirebonder_load.log` (a copy is also written to `%TEMP%`)
   records the resolved addon directory and whether `addWorkbench` succeeded — the first place to look
   when the workbench does not show up. A successful load looks like:

   ```log
   [2026-09-21 13:14:54] no __file__ in this namespace (NameError(...)), fall back to sys.path
   [2026-09-21 13:14:54] addon_dir  = ...\Mod\WireBonder
   [2026-09-21 13:14:54] package_dir= ...\Mod\WireBonder\WireBonder
   [2026-09-21 13:14:54] icon_dir   = ...\resources\icons (exists: True)
   [2026-09-21 13:14:54] language   = zh
   [2026-09-21 13:14:54] addWorkbench OK
   ```

   The `no __file__` on the first line is **normal** (see below).
3. **Pitfalls already hit (important when extending the addon)**:
   - FreeCAD executes `InitGui.py` through `exec(code, globals, locals)` where `globals` and `locals`
     are **not the same dictionary**: the namespace has **no `__file__`**, and a **top-level function
     that references a module-level variable raises `NameError`** (module-level assignments only land
     in `locals`, while name lookup inside functions uses `globals`).
     This addon therefore keeps all logic **inside a single function**, using only local/closure variables.
   - PySide6 (Qt6) enums are `enum.Flag`, so `int(QDialogButtonBox.Ok | Cancel)` raises a `TypeError`
     and you must use `.value`; PySide2 allows a plain `int()`.
   - `obj.Shape` is read-only: `obj.Shape.reverse()` raises `ReferenceError: This object is immutable`.
     Do `shape = obj.Shape.copy()` first, modify it, then assign it back.
4. If the two selected faces lie inside a `PartDesign::Body`, FreeCAD reports
   `Link(s) to object(s) ... go out of the allowed scope` when the object is created: this is a
   **warning, not an error**, and the geometry is still correct. To avoid it entirely, make the pads
   standalone Part objects, or put the generated object into an `App::Part` container at the same level
   as the Body.

## 7. File Structure

```text
src/                          # addon source (copied to <Mod>/WireBonder on install)
├── Init.py                   # non-GUI entry point, also marks the directory as an addon
├── InitGui.py                # workbench registration (single-function layout, writes the load log)
├── package.xml               # Addon Manager metadata (classname/icon/subdirectory)
├── README.md                 # this file: features / parameters / scripting / troubleshooting
└── WireBonder/               # Python package
    ├── __init__.py           # version and summary
    ├── i18n.py               # multi-language support (Chinese/English, follows the FreeCAD setting)
    ├── language_monitor.py   # runtime language-change monitor (switching needs no restart)
    ├── settings.py           # panel parameter persistence (remembers the last settings)
    ├── core.py               # geometry core (no GUI dependency): centroids/normals, bisector plane, loop, sweep, balls
    ├── features.py           # parametric objects WireBond / WireBondPlane + display styles
    ├── taskpanel.py          # parameter panel (PySide2 / PySide6 compatible)
    ├── commands.py           # FreeCAD commands, selection validation, degenerate-case pre-check
    └── resources/icons/      # WireBonder.svg / WireBond_Create.svg / WireBond_Plane.svg
```

## 8. Multi-Language Support

The addon UI **follows the FreeCAD language setting**:

| FreeCAD language | Addon display |
| --- | --- |
| Chinese (Simplified / any `zh*`) | **Chinese** |
| English | **English** |
| Any other language (German, Japanese, …) | **English** (fallback) |

Language detection order ([`i18n.detect_language()`](WireBonder/i18n.py)):

1. `FreeCADGui.getLocale()` — most accurate in GUI builds, returns e.g. `'Chinese (Simplified)'`;
2. the `Language` value under `User parameter:BaseApp/Preferences/General` — also works without a GUI;
3. `PySide.QtCore.QLocale.system().name()` — e.g. `zh_CN`;
4. all of the above failed → English.

### Switching the Language (no restart needed)

Change the language in FreeCAD (**Edit ▸ Preferences ▸ General ▸ Language**) and it takes effect
**immediately**: the workbench name, the toolbar/menu buttons and the parameter panel all follow
without restarting FreeCAD.

How it works ([`language_monitor.py`](WireBonder/language_monitor.py)):

- **two sources are watched**: the `Language` user parameter (written by the Preferences dialog) and
  `FreeCADGui.getLocale()` (the value the GUI actually uses) - either can change on its own;
- a parameter observer (`ParamGet(...).Attach()`) gives an immediate callback, backed by a 1.5 s poll timer;
- when the `Language` parameter changes, the addon calls `FreeCADGui.setLocale()` to push the new
  language to the GUI, keeping FreeCAD's own UI and the addon consistent - **changing the parameter
  alone does not update `getLocale()`**, which is the key detail;
- the workbench is re-registered (`Gui.removeWorkbench` + `Gui.addWorkbench`) so the menus are rebuilt;
- button texts must be applied **one event loop turn later**: while handling its `LanguageChange`
  event FreeCAD resets the QAction texts to untranslated strings, so an immediate assignment is
  overwritten. `QTimer.singleShot(0, ...)` defers the write until after that.

The startup log records the effective language and every switch:

```log
[2026-09-22 12:04:01] language   = zh
...
WireBond: language changed zh -> en
```

### Adding a New Language / Extending the Catalog

1. Open [`WireBonder/i18n.py`](WireBonder/i18n.py) — the Chinese catalog `_ZH` is keyed by the **English source text**;
2. To add a language, define e.g. `_JA = { "Wire Bond": "ワイヤボンド", ... }`, register it in
   `_TRANSLATIONS` and `LANGUAGES`, and recognize its language code inside `_normalize()`;
3. Write every new user-visible string in the source as `_("English text")`.

> Untranslated entries **fall back to the English source text**, so blanks or raw keys are never shown.

### Console Usage

```python
from WireBonder import i18n
print(i18n.language())          # 'zh' or 'en' (the auto-detected result)
i18n.set_language("en")         # force English temporarily (None restores auto-detection)
print(i18n.translate("Wire Bond"))
```

## 9. Related Documents

- Product design document (requirements, geometry algorithms, data model, architecture, test cases, pitfalls): [`../docs/freecad-wirebonder-prd.md`](../docs/freecad-wirebonder-prd.md)
- Installation guide (install / upgrade / uninstall / verify / troubleshoot): [`../README.md`](../README.md)

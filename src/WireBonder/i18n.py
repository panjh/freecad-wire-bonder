# -*- coding: utf-8 -*-
"""Minimal multi-language support (Chinese / English).

Rules
-----
* **Follows the FreeCAD language setting**, probed in this order:
  1. ``FreeCADGui.getLocale()``  (GUI builds, returns e.g. ``'Chinese (Simplified)'``)
  2. ``Language`` under ``User parameter:BaseApp/Preferences/General``  (works without a GUI)
  3. ``PySide``'s ``QLocale.system().name()``                          (e.g. ``zh_CN``)
* The **Chinese** language uses the Chinese catalogue;
* **Every other language** (English or any untranslated language) falls back to
  the **English** msgid.

Usage
-----
English source text is used as the msgid::

    from .i18n import _

    label = _("Wire Diameter")
    text = _("Centroid distance L = {:.3f} mm").format(length)

Sentences with placeholders also use the English text as msgid and the caller is
responsible for calling ``.format()``.
"""

__all__ = [
    "translate",
    "language",
    "set_language",
    "detect_language",
    "refresh",
    "LANGUAGES",
]

#: Supported language codes (everything except ``en`` falls back to English)
LANGUAGES = ("en", "zh")

# msgid (English) -> Chinese. This catalogue intentionally contains the only
# Chinese text in the Python sources: it is translation data, not a comment.
_ZH = {
    # ---------------- general ----------------
    "Wire Bond": "打线",
    "Wire Bonding": "打线辅助",
    "Cannot parse sub-element name: {}": "无法解析子元素名称: {}",
    "Face index out of range: {}": "面索引越界: {}",

    # ---------------- core.py: direction names / degenerate cases ----------------
    "face normal": "面法线",
    "centroid line": "质心连线",
    "normal bisector": "法线平分线",
    "plane normal": "平面法向",
    "path start tangent": "路径起始切线",
    "rotated Y axis": "偏转后的 y 轴",
    "rotated plane normal": "偏转后的平面法向",
    "{} has zero length; cannot determine its direction.":
        "{} 的长度为零, 无法确定方向。",
    "Selected sub-element {} is not a face; please select exactly two faces.":
        "选中的子元素 {} 不是平面, 请只选择两个面。",
    "Cannot obtain the face normal.": "无法获得面的法线方向。",
    "Cannot read the selected faces: {}": "无法读取选中的平面: {}",
    "{} has no face assigned.": "{} 未指定平面。",
    "The two face centroids coincide; cannot determine the connecting direction.":
        "两个平面的质心重合, 无法确定连线方向。",
    "The two face normals are 180 degrees apart, so no bisector exists; "
    "please select two faces with a consistent orientation.":
        "两个平面的法线互成 180 度, 平分线不存在; 请选择朝向一致的两个面。",
    "The centroid line is parallel to the normal bisector, so the plane is not "
    "unique; please select two faces whose normals differ in direction.":
        "质心连线方向与法线平分线平行, 无法唯一确定平面; "
        "请选择法线朝向不同的两个面。",
    "The centroid distance must be greater than zero.": "连线长度必须大于零。",
    "Clearance must not be negative.": "净空高度不能为负值。",
    "Wire diameter must be greater than zero.": "金线直径必须大于零。",
    "Ball diameter must be greater than zero.": "焊球直径必须大于零。",
    "WireBond: the swept result is not a valid solid; please check whether the "
    "wire diameter is too small.\n":
        "WireBond: 放样结果不是有效实体, 请检查金线直径是否过小。\n",

    # ---------------- features.py: property descriptions ----------------
    "First plane (Face)": "第一个平面 (面)",
    "Second plane (Face)": "第二个平面 (面)",
    "Wire diameter (default 20 um)": "金线直径 (默认 20 µm)",
    "Clearance: loop height above the centroid line (default 500 um)":
        "净空高度: 弧顶相对两质心连线的高度 (默认 500 µm)",
    "Loop peak position as a ratio of the centroid distance (0.05 - 0.95)":
        "拱顶位置占连线长度的比例 (0.05 - 0.95)",
    "Height ratio of the steep rise point near the start (0 - 1)":
        "出线陡升点的高度比例 (0 - 1)",
    "Height ratio of the descending point near the end (0 - 0.3)":
        "落线点的高度比例 (0 - 0.3)",
    "Create the gold wire solid (slower for very small diameters)":
        "生成金线实体 (直径很小时计算较慢)",
    "Also show the wire centreline": "同时显示金线的中心线",
    "Create bond balls at the two bond points": "在两个焊点处生成焊球 (bond ball)",
    "Bond ball diameter (default 50 um)": "焊球直径 (默认 50 µm)",
    "Rotation of the wire plane about the centroid line "
    "(0 deg = coincident with the bisector plane)":
        "走线平面绕两质心连线的偏转角 (0 度 = 与原平分平面重合)",
    "Margin of the rectangle beyond both ends of the centroid line":
        "矩形相对连线两端的外扩尺寸",
    "Rectangle half width = centroid distance x this factor":
        "矩形半宽 = 连线长度 × 该系数",

    # ---------------- taskpanel.py ----------------
    "Selected Faces": "选中的平面",
    "Face {}": "平面 {}",
    "{} : {}": "{} : {}",
    "Centroid {}  Normal {}   (global coordinates)":
        "质心 {}  法线 {}   (全局坐标)",
    "(cannot resolve: {})": "(无法解析: {})",
    "Centroid distance L = {:.3f} mm": "两质心间距 L = {:.3f} mm",
    "Span": "连线",
    "Note: the selected faces are inside the PartDesign Body ({}). The wire "
    "object is created outside of the Body, so FreeCAD reports\n"
    "\"Link(s) ... go out of the allowed scope\" - this is a scope-isolation "
    "warning and does not affect the geometry. To get rid of it, model the "
    "pads with the Part workbench (Part::Box, etc.).":
        "注意: 所选面位于 PartDesign Body ({}) 内部。生成的金线对象在 Body 之外, "
        "FreeCAD 会提示\n\"Link(s) ... go out of the allowed scope\" —— "
        "这是作用域隔离警告, 不影响几何结果。若不想再看到该提示, "
        "可把焊盘改用 Part 工作台建模 (Part::Box 等)。",
    "Wire Parameters": "金线参数",
    "Wire Diameter": "金线直径",
    "Clearance": "净空高度",
    "Peak Position Ratio": "拱顶位置比例",
    "Rise Height Ratio": "出线陡升比例",
    "Fall Height Ratio": "落线高度比例",
    "Bond Ball Diameter": "焊球直径",
    "Wire Plane Rotation": "走线平面偏转角",
    "Rotation of the wire plane about the centroid line: 0 deg is coincident\n"
    "with the bisector plane; a non-zero angle tilts the plane about the line":
        "走线平面绕两质心连线的偏转角: 0° 与原平分平面完全重合;\n"
        "非 0 时金线所在的平面绕连线旋转该角度",
    "Output Options": "输出选项",
    "Create the gold wire solid (slower for small diameters)":
        "生成金线实体 (直径很小时计算较慢)",
    "Also show the centreline": "同时显示中心线",
    "Create bond balls": "生成焊球 (bond ball)",
    "Create the bisector helper plane (construction reference, hidden after "
    "creation; off by default)":
        "创建平分辅助面 (构造参考, 生成后自动隐藏; 默认不创建)",
    "Note: the clearance ({:.0f} um) is larger than the centroid distance "
    "({:.0f} um);\nthe loop will look exaggerated - consider reducing the "
    "clearance.":
        "注意: 净空高度 ({:.0f} µm) 大于两质心间距 ({:.0f} µm),\n"
        "生成的弧线会比较夸张, 建议减小净空高度。",
    "Note: a 20 um gold wire is usually invisible at assembly scale, so only "
    "the centreline is generated by default;\n"
    "enable \"Create the gold wire solid\" to get a solid with the real "
    "diameter.\n"
    "The bisector helper plane is only a construction reference; it is hidden "
    "after creation and can be shown from the tree.":
        "提示: 20 µm 金线在整机尺度下通常不可见, 因此默认只生成中心线;\n"
        "勾选\"生成金线实体\"可得到真实直径的实体。\n"
        "平分辅助面仅为构造参考, 生成后会隐藏, 可在模型树中手动显示。",
    "No document is open.": "没有打开的文档。",
    "Failed to create the wire bond:\n{}": "生成金线失败:\n{}",

    # ---------------- commands.py ----------------
    "Create Wire Bond": "创建打线(金线)",
    "Create Bisector Plane": "创建平分辅助面",
    "Build the bisector plane of two faces and create a wire loop (gold wire) "
    "between the two face centroids.\nThe wire diameter and clearance can be "
    "set in the panel.":
        "由两个面构造平分平面, 并沿其对两质心连线生成打线弧 (金线)。\n"
        "金线直径与净空高度可在面板中设置。",
    "Only build the bisector plane of two faces, without creating a wire.":
        "只由两个面构造平分平面, 不生成金线。",
    "Please select two faces in the 3D view first (hold Ctrl for multi-select).\n"
    "Faces detected so far: {}.":
        "请先在 3D 视图中选中两个平面 (按住 Ctrl 多选)。\n当前只识别到 {} 个面。",
    "Too many faces selected ({}); please keep exactly two faces.":
        "选中的面过多 ({} 个), 请只保留两个平面。",
    "Wire Bond: centroid distance {:.3f} mm, plane normal ({:.3f}, {:.3f}, "
    "{:.3f})\n":
        "Wire Bond: 连线长度 {:.3f} mm, 平面法向 ({:.3f}, {:.3f}, {:.3f})\n",
    "Wire Bond: the selected faces belong to PartDesign Body ({}). The wire "
    "object is created outside of the Body, so FreeCAD reports \"Link(s) ... "
    "go out of the allowed scope\" - this is a scope-isolation warning and "
    "does not affect the geometry; to get rid of it, model the pads with the "
    "Part workbench (Part::Box, etc.).\n":
        "Wire Bond: 所选面位于 PartDesign Body ({}) 内部。生成的金线对象在 Body "
        "之外, FreeCAD 会提示 \"Link(s) ... go out of the allowed scope\" —— "
        "这是作用域隔离警告, 不影响几何结果; 若不想再看到该提示, "
        "可把焊盘改用 Part 工作台建模 (Part::Box 等)。\n",
    "Failed to create the bisector plane:\n{}": "创建平分平面失败:\n{}",

    # ---------------- InitGui.py ----------------
    "Build the bisector plane of two faces and create a wire loop (gold wire)":
        "由两个平面构造平分平面, 并生成打线弧 (金线)",
}

# English entries: the msgid itself is the English text, so no extra table is needed
_TRANSLATIONS = {"zh": _ZH}

_language = None


def _normalize(code):
    """Normalise any language identifier to ``zh`` or ``en``."""
    if not code:
        return "en"
    text = str(code).strip().lower()
    if text.startswith("zh") or "chinese" in text:
        return "zh"
    return "en"


def detect_language():
    """Detect the current FreeCAD language; returns ``'zh'`` or ``'en'``.

    Probe order: ``FreeCADGui.getLocale()`` -> the ``Language`` user parameter ->
    ``QLocale``. Falls back to English when all of them fail.
    """
    # 1) GUI interface (most accurate, only available in GUI builds)
    try:
        import FreeCADGui # type: ignore

        code = FreeCADGui.getLocale()
        if code:
            return _normalize(code)
    except Exception:
        pass

    # 2) FreeCAD user parameter (also available without a GUI)
    try:
        import FreeCAD # type: ignore

        param = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        code = param.GetString("Language", "")
        if code:
            return _normalize(code)
    except Exception:
        pass

    # 3) Qt system locale
    try:
        from PySide import QtCore # type: ignore

        return _normalize(QtCore.QLocale.system().name())
    except Exception:
        pass

    return "en"


def language():
    """Return the active language code (``'zh'`` or ``'en'``); the result is cached."""
    global _language
    if _language is None:
        _language = detect_language()
    return _language


def set_language(code):
    """Force a language (mainly for tests); pass ``None`` to restore auto-detection."""
    global _language
    _language = None if code is None else _normalize(code)


def refresh():
    """Drop the cached language and re-detect it.

    Returns a tuple ``(changed, previous, current)`` so callers can react only
    when the language really changed.  Used by the runtime language monitor, so
    that switching the language in FreeCAD takes effect without a restart.
    """
    global _language
    previous = _language
    _language = detect_language()
    return (_language != previous, previous, _language)


def translate(message):
    """Translate one message.

    Returns the Chinese entry in a Chinese environment when available, otherwise
    returns the English msgid **unchanged**.
    """
    if language() == "zh":
        return _ZH.get(message, message)
    return message


#: Short alias so the sources can simply write ``_("...")``
_ = translate

# -*- coding: utf-8 -*-
"""Task panel: collect wire diameter, clearance and related parameters, then create the wire bond."""

import traceback

import FreeCAD as App
import FreeCADGui as Gui

try:  # FreeCAD 1.x ships a PySide compatibility layer (backed by PySide6 / PySide2)
    from PySide import QtCore, QtWidgets # type: ignore
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets # type: ignore

from . import core, features, settings
from .i18n import translate as _


def _enum(group, name, fallback):
    """Look up a Qt enum member tolerating both PySide2 and PySide6 spellings.

    PySide2 exposes only the scoped form (``Qt.ScrollBarPolicy.ScrollBarAlwaysOff``)
    while PySide6 additionally provides the short form (``Qt.ScrollBarAlwaysOff``);
    the enum *values* are identical in both, so the numeric fallback is used when
    neither attribute exists.
    """
    scoped = getattr(getattr(QtCore.Qt, group, None), name, None)
    if scoped is not None:
        return scoped
    short = getattr(QtCore.Qt, name, None)
    if short is not None:
        return short
    return fallback


def _policy(name, fallback):
    """Shorthand for the ``Qt.ScrollBarPolicy`` group."""
    return _enum("ScrollBarPolicy", name, fallback)


def _fmt_number(value):
    """Format a coordinate compactly.

    A datum plane (``App::Plane``) is unbounded and reports ``1e100``-style
    coordinates; printing those with ``{:.2f}`` produces a number over a hundred
    characters long, which would stretch the panel far beyond the window. Large
    magnitudes are therefore shown in exponential notation.
    """
    try:
        number = float(value)
    except Exception:
        return "?"
    if abs(number) >= 1e6:
        return "{:.3g}".format(number)
    return "{:.2f}".format(number)


def _fmt_vector(vec):
    return "({}, {}, {})".format(
        _fmt_number(vec.x), _fmt_number(vec.y), _fmt_number(vec.z)
    )


def _wrap_label(text=""):
    """Create a word-wrapped label that can actually shrink.

    A wrapped ``QLabel`` reports a ``minimumSizeHint`` equal to its longest
    word, so long numbers or sentences would force the whole panel wider than
    the available space; with the horizontal scrollbar disabled that would clip
    the right hand side. Allowing the label to shrink to one pixel makes it wrap
    instead.
    """
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    label.setMinimumWidth(1)
    return label


class _WheelGuard(QtCore.QObject):
    """Swallow wheel events on a spin box and forward them to the scroll area.

    Without this, hovering over a field and scrolling changes its value - a very
    easy way to corrupt a parameter by accident. The event is instead handed to
    the enclosing scroll area so the panel still scrolls under the cursor.

    The guard is parented to the spin box it watches: ``installEventFilter()``
    does not take ownership, so without a parent the Python object would be
    garbage collected immediately and the filter would silently stop working.
    """

    def __init__(self, spinbox, scroll_area):
        super().__init__(spinbox)          # ownership keeps the filter alive
        self._scroll_area = scroll_area
        spinbox.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Wheel:
            area = self._scroll_area
            if area is not None and area is not obj:
                QtWidgets.QApplication.sendEvent(area.viewport(), event)
            return True
        return False


def _quantity_field(value, unit, decimals=2, minimum=None, maximum=None,
                    step=None, scroll_area=None):
    """Create a numeric input backed by FreeCAD's ``Gui::QuantitySpinBox``.

    This is the same widget the property editor uses, which gives each field
    three conveniences for free:

    * **free unit switching** - the unit is part of the stored value, so the
      user can type ``0.02 mm``, ``20 um`` or ``1 thou``, compare against a
      different unit in the context menu, and the display follows. Passing an
      empty ``unit`` yields a plain dimensionless number field;
    * **expressions** - arithmetic (``10*2``, ``0.5mm+10um``) and references to
      ``Spreadsheet`` cells are evaluated when the field is committed;
    * FreeCAD renders it itself, so the panel matches the property editor.

    ``value`` is expressed in ``unit`` (e.g. millimetres for a length). The
    widget picks the most readable prefix to display it with.
    """
    spin = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
    spin.setProperty("unit", unit)
    spin.setProperty("decimals", int(decimals))
    if minimum is not None:
        spin.setProperty("minimum", float(minimum))
    if maximum is not None:
        spin.setProperty("maximum", float(maximum))
    if step is not None:
        spin.setProperty("singleStep", float(step))
    # only commit on Enter / focus-out, so typing is not validated mid-keystroke
    spin.setProperty("keyboardTracking", False)
    _WheelGuard(spin, scroll_area)
    set_quantity(spin, value, unit)
    return spin


def _length_field(value_mm, decimals=3, minimum=None, maximum=None,
                  step=None, scroll_area=None):
    """Length input, stored in millimetres (FreeCAD's base unit)."""
    # minimum/maximum are given in millimetres as well
    spin = _quantity_field(value_mm, "mm", decimals=decimals,
                           minimum=minimum, maximum=maximum, step=step,
                           scroll_area=scroll_area)
    return spin


def _angle_field(value_deg, decimals=2, minimum=-180.0, maximum=180.0,
                 step=5.0, scroll_area=None):
    """Angle input, stored in degrees."""
    return _quantity_field(value_deg, "deg", decimals=decimals,
                           minimum=minimum, maximum=maximum, step=step,
                           scroll_area=scroll_area)


def _ratio_field(value, decimals=3, minimum=None, maximum=None, step=0.05,
                 scroll_area=None):
    """Dimensionless ratio input (no unit); expressions work here as well."""
    return _quantity_field(value, "", decimals=decimals, minimum=minimum,
                           maximum=maximum, step=step, scroll_area=scroll_area)


def get_quantity(spin, unit="mm"):
    """Read a field as a float in ``unit``, regardless of the displayed unit.

    The unit conversions go through ``App.Units`` - the module imports FreeCAD
    as ``App``, so the plain ``FreeCAD`` name is not available here.
    """
    raw = spin.property("value")
    try:
        return float(App.Units.Quantity(raw).getValueAs(unit))
    except Exception:
        return float(spin.property("rawValue"))


def set_quantity(spin, value, unit="mm"):
    """Set a field from a value given in ``unit``.

    Two details matter here, both established by measurement:

    * the quantity must be built with ``App.Units`` (the module aliases FreeCAD
      as ``App``); using ``FreeCAD.Units`` raised ``NameError``, which the
      fallback silently swallowed - the field then kept the bare number and the
      unit was lost, so ``0.001 in`` ended up as 0.001 mm instead of 0.0254 mm;
    * do **not** call ``interpretText()`` afterwards: it re-parses the line
      edit text (which lags behind the assignment) and overwrites the value.
    """
    try:
        spin.setProperty(
            "value", App.Units.Quantity("{} {}".format(float(value), unit)))
    except Exception:
        spin.setProperty("rawValue", float(value))


def get_length_mm(spin):
    """Read a length field as millimetres."""
    return get_quantity(spin, "mm")


def set_length_mm(spin, millimetres):
    """Set a length field from millimetres."""
    set_quantity(spin, millimetres, "mm")


def get_number(spin):
    """Read a dimensionless field."""
    return float(spin.property("rawValue"))


def set_number(spin, value):
    """Set a dimensionless field (see :func:`set_quantity` on ``interpretText``)."""
    spin.setProperty("rawValue", float(value))


class CollapsibleBox(QtWidgets.QWidget):
    """A group box whose content can be collapsed by clicking its title.

    ``QGroupBox`` cannot do this: making it checkable only *disables* the
    content instead of hiding it. This widget is a plain ``QWidget`` with a
    checkable ``QToolButton`` as the title bar.

    Qt enumerations are deliberately avoided (the collapse indicator is a text
    prefix and no arrow type or tool-button style is set), because PySide2 and
    PySide6 disagree about the short versus scoped enum forms.
    """

    _EXPANDED_MARK = "\u25be"    # small down triangle
    _COLLAPSED_MARK = "\u25b8"   # small right triangle

    def __init__(self, title, expanded=True, parent=None):
        super().__init__(parent)
        self._title = title
        #: optional callback(expanded) invoked on user interaction only
        self._on_state_changed = None

        self.toggle = QtWidgets.QToolButton(self)
        self.toggle.setCheckable(True)
        self.toggle.setAutoRaise(True)
        self.toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; }"
        )
        self.toggle.toggled.connect(self._on_toggled)

        self.body = QtWidgets.QWidget(self)
        self.content_layout = QtWidgets.QVBoxLayout(self.body)
        self.content_layout.setContentsMargins(8, 2, 2, 4)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)

        self._apply_state(bool(expanded), notify=False)

    # ------------------------------------------------------------------
    def _apply_state(self, expanded, notify=True):
        """Update the visual state without letting the toggle signal recurse.

        ``setChecked`` emits ``toggled``, which is connected to ``_on_toggled``;
        blocking the signal here keeps programmatic updates (construction,
        restore-defaults) from re-entering the toggle handler.
        """
        mark = self._EXPANDED_MARK if expanded else self._COLLAPSED_MARK
        self.toggle.setText("{} {}".format(mark, self._title))
        self.toggle.setToolTip(self._title)

        previous = self.toggle.blockSignals(True)
        try:
            self.toggle.setChecked(expanded)
        except Exception:
            pass
        finally:
            self.toggle.blockSignals(previous)

        self.body.setVisible(expanded)
        self.updateGeometry()

        if notify and self._on_state_changed is not None:
            self._on_state_changed(bool(expanded))

    def _on_toggled(self, checked):
        """User clicked the title: apply and notify."""
        mark = self._EXPANDED_MARK if checked else self._COLLAPSED_MARK
        self.toggle.setText("{} {}".format(mark, self._title))
        self.body.setVisible(checked)
        self.updateGeometry()
        if self._on_state_changed is not None:
            self._on_state_changed(bool(checked))

    def is_expanded(self):
        # authoritative source is the toggle, not isVisible(): a parent that is
        # itself hidden would make isVisible() report False for every child
        return bool(self.toggle.isChecked())

    def set_expanded(self, expanded):
        self._apply_state(bool(expanded), notify=False)

    def set_callback(self, callback):
        """Register ``callback(expanded)``, used to persist the UI state."""
        self._on_state_changed = callback


def containing_body(obj):
    """Return the innermost PartDesign::Body containing the object (None when not inside a Body).

    FreeCAD 1.x isolates the scope of a PartDesign Body: when an object outside
    the Body links directly to a sub-element (face/edge) inside it, FreeCAD prints

        Link(s) to object(s) '...' go out of the allowed scope '...'

    The message does not affect the geometry; we warn the user upfront and
    suggest how to avoid it.
    """
    if obj is None:
        return None
    for parent in getattr(obj, "InList", ()):
        if parent is not None and parent.TypeId == "PartDesign::Body":
            return parent
    return None


class WireBondTaskPanel:
    """Collect the parameters and create the WireBond / WireBondPlane objects."""

    def __init__(self, selection):
        # selection: [(obj1, "Face3"), (obj2, "Face7")]
        self.selection = list(selection)

        # Restore the values used last time, so repeated wire bonds do not need
        # the same numbers typed in again (stored in the FreeCAD user parameters).
        self.settings = settings.load_defaults()

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(_("Wire Bond"))
        self._build_ui()

    def collect_settings(self):
        """Read the current widget values back into a settings dict.

        Lengths are returned in millimetres (FreeCAD's base unit) no matter which
        unit the user chose to display them in.
        """
        start_mode, end_mode = self.selected_ball_modes()
        return {
            "wire_diameter": get_length_mm(self.diameter_um),
            "clearance": get_length_mm(self.clearance_um),
            "ball_diameter": get_length_mm(self.ball_diameter_um),
            "start_ball_mode": start_mode,
            "end_ball_mode": end_mode,
            "frustum_top_diameter": get_length_mm(self.frustum_top_um),
            "frustum_bottom_diameter": get_length_mm(self.frustum_bottom_um),
            "plane_rotation": get_quantity(self.plane_rotation_deg, "deg"),
            "peak_ratio": get_number(self.peak_ratio),
            "rise_angle": get_quantity(self.rise_angle, "deg"),
            "fall_angle": get_quantity(self.fall_angle, "deg"),
            "lead_distance": get_length_mm(self.lead_distance),
            "make_solid": self.make_solid.isChecked(),
            "show_centreline": self.show_centreline.isChecked(),
            "create_plane": self.create_plane.isChecked(),
        }

    def collect_ui_state(self):
        """Return which panel sections are currently expanded."""
        return {
            "ui_show_faces": self.section_faces.is_expanded(),
            "ui_show_params": self.section_params.is_expanded(),
            "ui_show_options": self.section_options.is_expanded(),
        }

    def _on_section_toggled(self, _expanded=None):
        """Persist the section layout immediately.

        Collapsing a section is a layout action, not a parameter edit, so it is
        stored right away instead of waiting for OK - otherwise a user who only
        collapses a section and cancels would not get it remembered.
        """
        try:
            settings.save_ui_state(**self.collect_ui_state())
        except Exception:
            pass

    def _make_mode_combo(self, current):
        """Build a bump-shape combo box (none / sphere / frustum)."""
        combo = QtWidgets.QComboBox()
        for value, label in (
                (core.BUMP_NONE, _("None")),
                (core.BUMP_SPHERE, _("Sphere")),
                (core.BUMP_FRUSTUM, _("Frustum"))):
            combo.addItem(label, value)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else combo.findData(
            core.BUMP_SPHERE))
        # a combo box is not a spin box, but the wheel would still change the
        # selection while merely scrolling past it
        _WheelGuard(combo, self._scroll)
        combo.currentIndexChanged.connect(self._on_ball_mode_changed)
        return combo

    @staticmethod
    def _combo_mode(combo):
        data = combo.currentData()
        return data if data in core.BUMP_MODES else core.BUMP_SPHERE

    def selected_ball_mode(self):
        """Shape at C1 (kept for compatibility with earlier callers)."""
        return self._combo_mode(self.start_ball_mode)

    def selected_ball_modes(self):
        """Return ``(mode_at_c1, mode_at_c2)``."""
        return (self._combo_mode(self.start_ball_mode),
                self._combo_mode(self.end_ball_mode))

    def _on_ball_mode_changed(self, _index=None):
        """Show only the diameter fields the selected bump shapes need.

        The two ends are considered together, because they share one set of
        diameter fields:

        * both ``none``      -> no diameter rows at all
        * any ``sphere``     -> the diameter row is needed
        * any ``frustum``    -> the top/bottom rows are needed
        """
        start_mode, end_mode = self.selected_ball_modes()
        modes = (start_mode, end_mode)
        wanted = []
        if any(m == core.BUMP_SPHERE for m in modes):
            wanted.append("diameter")
        if any(m == core.BUMP_FRUSTUM for m in modes):
            wanted.extend(("top", "bottom"))
        if start_mode == core.BUMP_NONE and end_mode == core.BUMP_NONE:
            wanted = []
        wanted = tuple(wanted)

        for label, field, name in self._ball_rows:
            visible = name in wanted
            label.setVisible(visible)
            field.setVisible(visible)
        # let the form layout reclaim the freed space immediately
        for parent in (field.parentWidget() for _l, field, _n in self._ball_rows):
            if parent is not None:
                parent.updateGeometry()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # The panel can exceed the available height; everything scrolls inside
        # a QScrollArea so no control is ever cut off.
        outer = QtWidgets.QVBoxLayout(self.form)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QtWidgets.QScrollArea(self.form)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(_policy("ScrollBarAlwaysOff", 1))
        content = QtWidgets.QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        # remembered so the wheel guard can forward scrolling to the panel
        self._scroll = scroll

        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- section: selected faces (collapsible) ---
        self.section_faces = CollapsibleBox(
            _("Selected Faces"), bool(self.settings["ui_show_faces"])
        )
        self.section_faces.set_callback(self._on_section_toggled)
        info = QtWidgets.QWidget()
        info_layout = QtWidgets.QFormLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        self.section_faces.content_layout.addWidget(info)
        centres = []
        for index, (obj, sub) in enumerate(self.selection, start=1):
            text = "{} : {}".format(obj.Label, sub)
            try:
                # global_face is mandatory here: it adds the parent container
                # (App::Part / Body ...) transform, otherwise the centroid shown
                # for a part inside an assembly would be in local coordinates
                # and look wrong
                face = core.global_face(obj, sub)
                centre, normal = core.face_centre_and_normal(face)
                centres.append(centre)
                text += "\n" + _(
                    "Centroid {}  Normal {}   (global coordinates)"
                ).format(_fmt_vector(centre), _fmt_vector(normal))
            except Exception as exc:
                text += "\n" + _("(cannot resolve: {})").format(exc)
            label = _wrap_label(text)
            info_layout.addRow(_("Face {}").format(index), label)

        span = None
        if len(centres) == 2:
            span = (centres[1] - centres[0]).Length
            span_label = _wrap_label(
                _("Centroid distance L = {:.3f} mm").format(span)
            )
            info_layout.addRow(_("Span"), span_label)
        layout.addWidget(self.section_faces)

        body_names = []
        for obj, _sub in self.selection:
            body = containing_body(obj)
            if body is not None and body.Name not in body_names:
                body_names.append(body.Name)
        if body_names:
            scope_note = _wrap_label(
                _("Note: the selected faces are inside the PartDesign Body "
                  "({}). The wire object is created outside of the Body, so "
                  "FreeCAD reports\n\"Link(s) ... go out of the allowed scope\" "
                  "- this is a scope-isolation warning and does not affect the "
                  "geometry. To get rid of it, model the pads with the Part "
                  "workbench (Part::Box, etc.).").format(", ".join(body_names))
            )
            scope_note.setStyleSheet("color: #B26500;")
            layout.addWidget(scope_note)

        # --- section: wire parameters (collapsible) ---
        self.section_params = CollapsibleBox(
            _("Wire Parameters"), bool(self.settings["ui_show_params"])
        )
        self.section_params.set_callback(self._on_section_toggled)
        params = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(params)
        form.setContentsMargins(0, 0, 0, 0)
        self.section_params.content_layout.addWidget(params)

        # All numeric fields use FreeCAD's own Gui::QuantitySpinBox, the same
        # widget as the property editor: the unit is part of the value (so the
        # user may enter "0.02 mm", "20 um" or switch via the context menu),
        # expressions such as "10*2" are evaluated, and scrolling over a field
        # is redirected to the panel instead of changing the value.
        self.diameter_um = _length_field(
            self.settings["wire_diameter"], decimals=3,
            minimum=0.0001, maximum=0.5, step=0.001, scroll_area=self._scroll)
        self.diameter_um.setToolTip(
            _("Gold wire diameter, e.g. 20 um. Any length unit works; "
              "expressions such as 0.01*2 are accepted."))
        form.addRow(_("Wire Diameter"), self.diameter_um)

        self.clearance_um = _length_field(
            self.settings["clearance"], decimals=4,
            minimum=0.0, maximum=100.0, step=0.01, scroll_area=self._scroll)
        self.clearance_um.setToolTip(
            _("Loop height above the centroid line, e.g. 0.5 mm or 500 um. "
              "Any length unit works."))
        form.addRow(_("Clearance"), self.clearance_um)

        self.plane_rotation_deg = _angle_field(
            self.settings["plane_rotation"], decimals=2,
            minimum=-180.0, maximum=180.0, step=5.0, scroll_area=self._scroll)
        self.plane_rotation_deg.setToolTip(
            _("Rotation of the wire plane about the centroid line: 0 deg is "
              "coincident\nwith the bisector plane; a non-zero angle tilts the "
              "plane about the line")
        )
        form.addRow(_("Wire Plane Rotation"), self.plane_rotation_deg)

        self.peak_ratio = _ratio_field(
            self.settings["peak_ratio"], decimals=3,
            minimum=0.05, maximum=0.95, step=0.05, scroll_area=self._scroll)
        self.peak_ratio.setToolTip(
            _("Position of the loop peak along the centroid line, as a ratio "
              "(0.5 = symmetric). Expressions are accepted."))
        form.addRow(_("Peak Position Ratio"), self.peak_ratio)

        # Angles, not height ratios: 0 deg points along the line between the
        # pads, 90 deg is perpendicular to it (straight up).
        self.rise_angle = _angle_field(
            self.settings["rise_angle"], decimals=1,
            minimum=0.0, maximum=89.0, step=5.0, scroll_area=self._scroll)
        self.rise_angle.setToolTip(
            _("Angle at which the wire leaves the first pad, measured from the "
              "line between the pads.\n0 deg = along that line towards the "
              "second pad, 90 deg = perpendicular (straight up)."))
        form.addRow(_("Rise Angle"), self.rise_angle)

        self.fall_angle = _angle_field(
            self.settings["fall_angle"], decimals=1,
            minimum=0.0, maximum=89.0, step=5.0, scroll_area=self._scroll)
        self.fall_angle.setToolTip(
            _("Angle at which the wire reaches the second pad, measured from "
              "the line between the pads.\n0 deg = along that line towards the "
              "first pad, 90 deg = perpendicular (straight up)."))
        form.addRow(_("Fall Angle"), self.fall_angle)

        # How far from each pad the entry/exit control point sits. Together with
        # the rise/fall ratios it fixes the entry and exit angles.
        self.lead_distance = _length_field(
            self.settings.get("lead_distance", core.DEFAULT_LEAD_DISTANCE),
            decimals=4, minimum=0.0, maximum=5.0, step=0.001,
            scroll_area=self._scroll)
        self.lead_distance.setToolTip(
            _("Horizontal distance from each pad to its entry/exit control "
              "point.\nWith the rise/fall ratios it determines the angle at "
              "which the wire leaves C1 and lands on C2:\n"
              "slope = ratio × clearance / distance, so a smaller distance "
              "gives a steeper approach."))
        form.addRow(_("Lead Distance"), self.lead_distance)

        # --- bond bumps: one shape selector per bond point ---
        # C1 is the first bond point, C2 the second; they may use different
        # shapes (for example a ball on the chip and a wedge on the substrate).
        self.start_ball_mode = self._make_mode_combo(
            self.settings.get("start_ball_mode", core.BUMP_SPHERE))
        self.start_ball_mode.setToolTip(
            _("Shape of the bump at the first bond point (C1)."))
        form.addRow(_("Bond Bump at C1"), self.start_ball_mode)

        self.end_ball_mode = self._make_mode_combo(
            self.settings.get("end_ball_mode", core.BUMP_SPHERE))
        self.end_ball_mode.setToolTip(
            _("Shape of the bump at the second bond point (C2)."))
        form.addRow(_("Bond Bump at C2"), self.end_ball_mode)

        # Field labels are plain QLabels: the shrinkable _wrap_label() used for
        # the long notes would let the label column collapse to one character
        # per line, which is unreadable next to a form field.
        #
        # diameter row (sphere) -----------------------------------------
        self.ball_diameter_label = QtWidgets.QLabel(_("Ball Diameter"))
        self.ball_diameter_um = _length_field(
            self.settings["ball_diameter"], decimals=4,
            minimum=0.001, maximum=20.0, step=0.005, scroll_area=self._scroll)
        self.ball_diameter_um.setToolTip(
            _("Sphere: the ball diameter. Frustum: the bump height. "
              "Any length unit works."))
        form.addRow(self.ball_diameter_label, self.ball_diameter_um)

        # top / bottom rows (frustum) -----------------------------------
        self.frustum_top_label = QtWidgets.QLabel(_("Top Diameter"))
        self.frustum_top_um = _length_field(
            self.settings.get("frustum_top_diameter", core.DEFAULT_BALL_DIAMETER),
            decimals=4, minimum=0.001, maximum=20.0, step=0.005,
            scroll_area=self._scroll)
        self.frustum_top_um.setToolTip(
            _("Frustum: diameter of the end away from the pad."))
        form.addRow(self.frustum_top_label, self.frustum_top_um)

        self.frustum_bottom_label = QtWidgets.QLabel(_("Bottom Diameter"))
        self.frustum_bottom_um = _length_field(
            self.settings.get("frustum_bottom_diameter",
                              core.DEFAULT_BALL_DIAMETER),
            decimals=4, minimum=0.001, maximum=20.0, step=0.005,
            scroll_area=self._scroll)
        self.frustum_bottom_um.setToolTip(
            _("Frustum: diameter of the end sitting on the pad."))
        form.addRow(self.frustum_bottom_label, self.frustum_bottom_um)

        # show only the rows the selected shape actually uses
        self._ball_rows = (
            (self.ball_diameter_label, self.ball_diameter_um, "diameter"),
            (self.frustum_top_label, self.frustum_top_um, "top"),
            (self.frustum_bottom_label, self.frustum_bottom_um, "bottom"),
        )
        self._on_ball_mode_changed()

        layout.addWidget(self.section_params)

        # --- section: output options (collapsible) ---
        self.section_options = CollapsibleBox(
            _("Output Options"), bool(self.settings["ui_show_options"])
        )
        self.section_options.set_callback(self._on_section_toggled)
        options = QtWidgets.QWidget()
        opt_layout = QtWidgets.QVBoxLayout(options)
        opt_layout.setContentsMargins(0, 0, 0, 0)
        self.section_options.content_layout.addWidget(options)

        self.make_solid = QtWidgets.QCheckBox(
            _("Create the gold wire solid (slower for small diameters)")
        )
        self.make_solid.setChecked(bool(self.settings["make_solid"]))
        opt_layout.addWidget(self.make_solid)

        self.show_centreline = QtWidgets.QCheckBox(_("Also show the centreline"))
        self.show_centreline.setChecked(bool(self.settings["show_centreline"]))
        opt_layout.addWidget(self.show_centreline)

        self.create_plane = QtWidgets.QCheckBox(
            _("Create the bisector helper plane (construction reference, hidden "
              "after creation; off by default)")
        )
        self.create_plane.setChecked(bool(self.settings["create_plane"]))
        opt_layout.addWidget(self.create_plane)

        layout.addWidget(self.section_options)

        clearance_mm = get_length_mm(self.clearance_um)
        if span is not None and clearance_mm > span:
            span_note = _wrap_label(
                _("Note: the clearance ({:.0f} um) is larger than the centroid "
                  "distance ({:.0f} um);\nthe loop will look exaggerated - "
                  "consider reducing the clearance.").format(
                    clearance_mm * 1000.0, span * 1000.0
                )
            )
            span_note.setStyleSheet("color: #B26500;")
            layout.addWidget(span_note)

        # The panel remembers the last used values; offer a way back to the
        # built-in defaults (which also clears the stored settings).
        self.restore_button = QtWidgets.QPushButton(_("Restore Defaults"))
        self.restore_button.setToolTip(
            _("Reset the panel to the built-in defaults and forget the stored "
              "settings.")
        )
        self.restore_button.clicked.connect(self._restore_defaults)
        layout.addWidget(self.restore_button)

        hint = _wrap_label(
            _("Note: a 20 um gold wire is usually invisible at assembly scale, "
              "so only the centreline is generated by default;\n"
              "enable \"Create the gold wire solid\" to get a solid with the "
              "real diameter.\n"
              "The bisector helper plane is only a construction reference; it "
              "is hidden after creation and can be shown from the tree.\n"
              "The panel reopens with the values used last time;\n"
              "click a section title to collapse or expand it.")
        )
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)
        layout.addStretch(1)

    def _restore_defaults(self):
        """Reset every widget to the built-in default and drop the stored values."""
        defaults = settings.Settings.defaults()
        settings.clear()

        set_length_mm(self.diameter_um, defaults["wire_diameter"])
        set_length_mm(self.clearance_um, defaults["clearance"])
        set_length_mm(self.ball_diameter_um, defaults["ball_diameter"])
        set_length_mm(self.frustum_top_um, defaults["frustum_top_diameter"])
        set_length_mm(self.frustum_bottom_um, defaults["frustum_bottom_diameter"])
        set_length_mm(self.lead_distance, defaults["lead_distance"])
        for combo, key in ((self.start_ball_mode, "start_ball_mode"),
                           (self.end_ball_mode, "end_ball_mode")):
            index = combo.findData(defaults[key])
            combo.setCurrentIndex(index if index >= 0 else
                                  combo.findData(core.BUMP_SPHERE))
        self._on_ball_mode_changed()
        set_quantity(self.plane_rotation_deg, defaults["plane_rotation"], "deg")
        set_number(self.peak_ratio, defaults["peak_ratio"])
        set_quantity(self.rise_angle, defaults["rise_angle"], "deg")
        set_quantity(self.fall_angle, defaults["fall_angle"], "deg")
        self.make_solid.setChecked(bool(defaults["make_solid"]))
        self.show_centreline.setChecked(bool(defaults["show_centreline"]))
        self.create_plane.setChecked(bool(defaults["create_plane"]))

    # ------------------------------------------------------------------
    # TaskPanel protocol
    # ------------------------------------------------------------------
    def getStandardButtons(self):
        """Return the panel buttons.

        Compatibility note: PySide2 enums are plain ints, while PySide6 (Qt6)
        enums are ``enum.Flag``, so ``int(flag)`` raises a TypeError and
        ``.value`` must be used instead.
        """
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        try:
            return int(buttons)
        except TypeError:
            return int(buttons.value)

    def accept(self):
        doc = App.ActiveDocument
        if doc is None:
            QtWidgets.QMessageBox.warning(
                None, _("Wire Bond"), _("No document is open.")
            )
            return False

        (obj1, sub1), (obj2, sub2) = self.selection

        doc.openTransaction("Create Wire Bond")
        try:
            wire = doc.addObject("Part::FeaturePython", "WireBond")
            features.WireBondFeature(wire)
            if wire.ViewObject is not None:
                features.ViewProviderWireBond(wire.ViewObject)

            wire.Face1 = (obj1, sub1)
            wire.Face2 = (obj2, sub2)
            # values are read as millimetres and handed over with an explicit
            # unit, so the object does not depend on the field's display unit
            current = self.collect_settings()
            wire.WireDiameter = "{} mm".format(current["wire_diameter"])
            wire.Clearance = "{} mm".format(current["clearance"])
            wire.PeakRatio = current["peak_ratio"]
            wire.RiseAngle = "{} deg".format(current["rise_angle"])
            wire.FallAngle = "{} deg".format(current["fall_angle"])
            wire.MakeSolid = self.make_solid.isChecked()
            wire.ShowCentreline = self.show_centreline.isChecked()
            wire.BallDiameter = "{} mm".format(current["ball_diameter"])
            if hasattr(wire, "StartBallMode"):
                wire.StartBallMode = current["start_ball_mode"]
                wire.EndBallMode = current["end_ball_mode"]
            if hasattr(wire, "LeadDistance"):
                wire.LeadDistance = "{} mm".format(current["lead_distance"])
            if hasattr(wire, "FrustumTopDiameter"):
                wire.FrustumTopDiameter = "{} mm".format(
                    current["frustum_top_diameter"])
                wire.FrustumBottomDiameter = "{} mm".format(
                    current["frustum_bottom_diameter"])
            wire.PlaneRotation = "{} deg".format(current["plane_rotation"])

            plane = None
            if self.create_plane.isChecked():
                plane = doc.addObject("Part::FeaturePython", "WireBondPlane")
                features.BisectorPlaneFeature(plane)
                if plane.ViewObject is not None:
                    features.ViewProviderBisectorPlane(plane.ViewObject)
                plane.Face1 = (obj1, sub1)
                plane.Face2 = (obj2, sub2)
                plane.PlaneRotation = "{} deg".format(current["plane_rotation"])

            doc.recompute()

            # the bisector plane is only a construction helper: hide it right away
            if plane is not None and plane.ViewObject is not None:
                plane.ViewObject.Visibility = False

            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            # The message box alone is not enough to diagnose a failure, so the
            # full traceback also goes to the report view.
            detail = traceback.format_exc()
            App.Console.PrintError(
                "WireBond: failed to create the wire bond.\n" + detail
            )
            QtWidgets.QMessageBox.critical(
                None, _("Wire Bond"),
                _("Failed to create the wire bond:\n{}\n\n"
                  "The full traceback was written to the report view.").format(exc)
            )
            return False

        # Remember what was used, so the next panel opens with the same values.
        settings.save_defaults(**self.collect_settings())
        settings.save_ui_state(**self.collect_ui_state())

        try:
            Gui.ActiveDocument.ActiveView.viewIsometric()
        except Exception:
            pass
        Gui.Control.closeDialog()
        return True

    def reject(self):
        Gui.Control.closeDialog()
        return True

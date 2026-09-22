# -*- coding: utf-8 -*-
"""Task panel: collect wire diameter, clearance and related parameters, then create the wire bond."""

import FreeCAD as App
import FreeCADGui as Gui

try:  # FreeCAD 1.x ships a PySide compatibility layer (backed by PySide6 / PySide2)
    from PySide import QtCore, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets

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
        """Read the current widget values back into a settings dict (in mm)."""
        return {
            "wire_diameter": self.diameter_um.value() / 1000.0,
            "clearance": self.clearance_um.value() / 1000.0,
            "ball_diameter": self.ball_diameter_um.value() / 1000.0,
            "plane_rotation": self.plane_rotation_deg.value(),
            "peak_ratio": self.peak_ratio.value(),
            "rise_ratio": self.rise_ratio.value(),
            "fall_ratio": self.fall_ratio.value(),
            "make_solid": self.make_solid.isChecked(),
            "show_centreline": self.show_centreline.isChecked(),
            "make_balls": self.make_balls.isChecked(),
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

        self.diameter_um = QtWidgets.QDoubleSpinBox()
        self.diameter_um.setDecimals(2)
        self.diameter_um.setRange(0.1, 500.0)
        self.diameter_um.setValue(self.settings["wire_diameter"] * 1000.0)
        self.diameter_um.setSuffix(" µm")
        form.addRow(_("Wire Diameter"), self.diameter_um)

        self.clearance_um = QtWidgets.QDoubleSpinBox()
        self.clearance_um.setDecimals(1)
        self.clearance_um.setRange(0.0, 100000.0)
        self.clearance_um.setValue(self.settings["clearance"] * 1000.0)
        self.clearance_um.setSuffix(" µm")
        form.addRow(_("Clearance"), self.clearance_um)

        self.plane_rotation_deg = QtWidgets.QDoubleSpinBox()
        self.plane_rotation_deg.setDecimals(1)
        self.plane_rotation_deg.setRange(-180.0, 180.0)
        self.plane_rotation_deg.setSingleStep(5.0)
        self.plane_rotation_deg.setValue(self.settings["plane_rotation"])
        self.plane_rotation_deg.setSuffix(" °")
        self.plane_rotation_deg.setToolTip(
            _("Rotation of the wire plane about the centroid line: 0 deg is "
              "coincident\nwith the bisector plane; a non-zero angle tilts the "
              "plane about the line")
        )
        form.addRow(_("Wire Plane Rotation"), self.plane_rotation_deg)

        self.peak_ratio = QtWidgets.QDoubleSpinBox()
        self.peak_ratio.setDecimals(2)
        self.peak_ratio.setSingleStep(0.05)
        self.peak_ratio.setRange(0.05, 0.95)
        self.peak_ratio.setValue(self.settings["peak_ratio"])
        form.addRow(_("Peak Position Ratio"), self.peak_ratio)

        self.rise_ratio = QtWidgets.QDoubleSpinBox()
        self.rise_ratio.setDecimals(2)
        self.rise_ratio.setSingleStep(0.05)
        self.rise_ratio.setRange(0.0, 1.0)
        self.rise_ratio.setValue(self.settings["rise_ratio"])
        form.addRow(_("Rise Height Ratio"), self.rise_ratio)

        self.fall_ratio = QtWidgets.QDoubleSpinBox()
        self.fall_ratio.setDecimals(2)
        self.fall_ratio.setSingleStep(0.05)
        self.fall_ratio.setRange(0.0, 0.60)
        self.fall_ratio.setValue(self.settings["fall_ratio"])
        form.addRow(_("Fall Height Ratio"), self.fall_ratio)

        self.ball_diameter_um = QtWidgets.QDoubleSpinBox()
        self.ball_diameter_um.setDecimals(1)
        self.ball_diameter_um.setRange(1.0, 20000.0)
        self.ball_diameter_um.setValue(self.settings["ball_diameter"] * 1000.0)
        self.ball_diameter_um.setSuffix(" µm")
        form.addRow(_("Bond Ball Diameter"), self.ball_diameter_um)

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

        self.make_balls = QtWidgets.QCheckBox(_("Create bond balls"))
        self.make_balls.setChecked(bool(self.settings["make_balls"]))
        opt_layout.addWidget(self.make_balls)

        self.create_plane = QtWidgets.QCheckBox(
            _("Create the bisector helper plane (construction reference, hidden "
              "after creation; off by default)")
        )
        self.create_plane.setChecked(bool(self.settings["create_plane"]))
        opt_layout.addWidget(self.create_plane)

        layout.addWidget(self.section_options)

        if span is not None and self.clearance_um.value() / 1000.0 > span:
            span_note = _wrap_label(
                _("Note: the clearance ({:.0f} um) is larger than the centroid "
                  "distance ({:.0f} um);\nthe loop will look exaggerated - "
                  "consider reducing the clearance.").format(
                    self.clearance_um.value(), span * 1000.0
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

        self.diameter_um.setValue(defaults["wire_diameter"] * 1000.0)
        self.clearance_um.setValue(defaults["clearance"] * 1000.0)
        self.ball_diameter_um.setValue(defaults["ball_diameter"] * 1000.0)
        self.plane_rotation_deg.setValue(defaults["plane_rotation"])
        self.peak_ratio.setValue(defaults["peak_ratio"])
        self.rise_ratio.setValue(defaults["rise_ratio"])
        self.fall_ratio.setValue(defaults["fall_ratio"])
        self.make_solid.setChecked(bool(defaults["make_solid"]))
        self.show_centreline.setChecked(bool(defaults["show_centreline"]))
        self.make_balls.setChecked(bool(defaults["make_balls"]))
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
            wire.WireDiameter = "{} um".format(self.diameter_um.value())
            wire.Clearance = "{} um".format(self.clearance_um.value())
            wire.PeakRatio = self.peak_ratio.value()
            wire.RiseRatio = self.rise_ratio.value()
            wire.FallRatio = self.fall_ratio.value()
            wire.MakeSolid = self.make_solid.isChecked()
            wire.ShowCentreline = self.show_centreline.isChecked()
            wire.MakeBalls = self.make_balls.isChecked()
            wire.BallDiameter = "{} um".format(self.ball_diameter_um.value())
            wire.PlaneRotation = "{} deg".format(self.plane_rotation_deg.value())

            plane = None
            if self.create_plane.isChecked():
                plane = doc.addObject("Part::FeaturePython", "WireBondPlane")
                features.BisectorPlaneFeature(plane)
                if plane.ViewObject is not None:
                    features.ViewProviderBisectorPlane(plane.ViewObject)
                plane.Face1 = (obj1, sub1)
                plane.Face2 = (obj2, sub2)
                plane.PlaneRotation = "{} deg".format(self.plane_rotation_deg.value())

            doc.recompute()

            # the bisector plane is only a construction helper: hide it right away
            if plane is not None and plane.ViewObject is not None:
                plane.ViewObject.Visibility = False

            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(
                None, _("Wire Bond"), _("Failed to create the wire bond:\n{}").format(exc)
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

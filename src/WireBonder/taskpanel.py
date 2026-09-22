# -*- coding: utf-8 -*-
"""Task panel: collect wire diameter, clearance and related parameters, then create the wire bond."""

import FreeCAD as App
import FreeCADGui as Gui

try:  # FreeCAD 1.x ships a PySide compatibility layer (backed by PySide6 / PySide2)
    from PySide import QtCore, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets

from . import core, features
from .i18n import translate as _


def _fmt_vector(vec):
    return "({:.2f}, {:.2f}, {:.2f})".format(vec.x, vec.y, vec.z)


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

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(_("Wire Bond"))
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self.form)

        info = QtWidgets.QGroupBox(_("Selected Faces"))
        info_layout = QtWidgets.QFormLayout(info)
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
            label = QtWidgets.QLabel(text)
            label.setWordWrap(True)
            info_layout.addRow(_("Face {}").format(index), label)

        span = None
        if len(centres) == 2:
            span = (centres[1] - centres[0]).Length
            span_label = QtWidgets.QLabel(
                _("Centroid distance L = {:.3f} mm").format(span)
            )
            span_label.setWordWrap(True)
            info_layout.addRow(_("Span"), span_label)
        layout.addWidget(info)

        body_names = []
        for obj, _sub in self.selection:
            body = containing_body(obj)
            if body is not None and body.Name not in body_names:
                body_names.append(body.Name)
        if body_names:
            scope_note = QtWidgets.QLabel(
                _("Note: the selected faces are inside the PartDesign Body "
                  "({}). The wire object is created outside of the Body, so "
                  "FreeCAD reports\n\"Link(s) ... go out of the allowed scope\" "
                  "- this is a scope-isolation warning and does not affect the "
                  "geometry. To get rid of it, model the pads with the Part "
                  "workbench (Part::Box, etc.).").format(", ".join(body_names))
            )
            scope_note.setWordWrap(True)
            scope_note.setStyleSheet("color: #B26500;")
            layout.addWidget(scope_note)

        params = QtWidgets.QGroupBox(_("Wire Parameters"))
        form = QtWidgets.QFormLayout(params)

        self.diameter_um = QtWidgets.QDoubleSpinBox()
        self.diameter_um.setDecimals(2)
        self.diameter_um.setRange(0.1, 500.0)
        self.diameter_um.setValue(core.DEFAULT_WIRE_DIAMETER * 1000.0)
        self.diameter_um.setSuffix(" µm")
        form.addRow(_("Wire Diameter"), self.diameter_um)

        self.clearance_um = QtWidgets.QDoubleSpinBox()
        self.clearance_um.setDecimals(1)
        self.clearance_um.setRange(0.0, 100000.0)
        self.clearance_um.setValue(core.DEFAULT_CLEARANCE * 1000.0)
        self.clearance_um.setSuffix(" µm")
        form.addRow(_("Clearance"), self.clearance_um)

        self.plane_rotation_deg = QtWidgets.QDoubleSpinBox()
        self.plane_rotation_deg.setDecimals(1)
        self.plane_rotation_deg.setRange(-180.0, 180.0)
        self.plane_rotation_deg.setSingleStep(5.0)
        self.plane_rotation_deg.setValue(core.DEFAULT_PLANE_ROTATION)
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
        self.peak_ratio.setValue(core.DEFAULT_PEAK_RATIO)
        form.addRow(_("Peak Position Ratio"), self.peak_ratio)

        self.rise_ratio = QtWidgets.QDoubleSpinBox()
        self.rise_ratio.setDecimals(2)
        self.rise_ratio.setSingleStep(0.05)
        self.rise_ratio.setRange(0.0, 1.0)
        self.rise_ratio.setValue(core.DEFAULT_RISE_RATIO)
        form.addRow(_("Rise Height Ratio"), self.rise_ratio)

        self.fall_ratio = QtWidgets.QDoubleSpinBox()
        self.fall_ratio.setDecimals(2)
        self.fall_ratio.setSingleStep(0.05)
        self.fall_ratio.setRange(0.0, 0.60)
        self.fall_ratio.setValue(core.DEFAULT_FALL_RATIO)
        form.addRow(_("Fall Height Ratio"), self.fall_ratio)

        self.ball_diameter_um = QtWidgets.QDoubleSpinBox()
        self.ball_diameter_um.setDecimals(1)
        self.ball_diameter_um.setRange(1.0, 20000.0)
        self.ball_diameter_um.setValue(core.DEFAULT_BALL_DIAMETER * 1000.0)
        self.ball_diameter_um.setSuffix(" µm")
        form.addRow(_("Bond Ball Diameter"), self.ball_diameter_um)

        layout.addWidget(params)

        options = QtWidgets.QGroupBox(_("Output Options"))
        opt_layout = QtWidgets.QVBoxLayout(options)

        self.make_solid = QtWidgets.QCheckBox(
            _("Create the gold wire solid (slower for small diameters)")
        )
        self.make_solid.setChecked(False)
        opt_layout.addWidget(self.make_solid)

        self.show_centreline = QtWidgets.QCheckBox(_("Also show the centreline"))
        self.show_centreline.setChecked(True)
        opt_layout.addWidget(self.show_centreline)

        self.make_balls = QtWidgets.QCheckBox(_("Create bond balls"))
        self.make_balls.setChecked(True)
        opt_layout.addWidget(self.make_balls)

        self.create_plane = QtWidgets.QCheckBox(
            _("Create the bisector helper plane (construction reference, hidden "
              "after creation; off by default)")
        )
        self.create_plane.setChecked(False)
        opt_layout.addWidget(self.create_plane)

        layout.addWidget(options)

        if span is not None and self.clearance_um.value() / 1000.0 > span:
            span_note = QtWidgets.QLabel(
                _("Note: the clearance ({:.0f} um) is larger than the centroid "
                  "distance ({:.0f} um);\nthe loop will look exaggerated - "
                  "consider reducing the clearance.").format(
                    self.clearance_um.value(), span * 1000.0
                )
            )
            span_note.setStyleSheet("color: #B26500;")
            span_note.setWordWrap(True)
            layout.addWidget(span_note)

        hint = QtWidgets.QLabel(
            _("Note: a 20 um gold wire is usually invisible at assembly scale, "
              "so only the centreline is generated by default;\n"
              "enable \"Create the gold wire solid\" to get a solid with the "
              "real diameter.\n"
              "The bisector helper plane is only a construction reference; it "
              "is hidden after creation and can be shown from the tree.")
        )
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)
        layout.addStretch(1)

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

        try:
            Gui.ActiveDocument.ActiveView.viewIsometric()
        except Exception:
            pass
        Gui.Control.closeDialog()
        return True

    def reject(self):
        Gui.Control.closeDialog()
        return True

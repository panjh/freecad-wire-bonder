# -*- coding: utf-8 -*-
"""Parametric objects: the gold wire (WireBond) and the bisector plane (WireBondPlane).

Both are ``Part::FeaturePython`` objects that reference the two faces selected
by the user through ``App::PropertyLinkSub``. After any parameter change (wire
diameter, the loop control points, ...) FreeCAD re-runs ``execute()``
automatically and rebuilds the geometry.
"""

import os

import FreeCAD as App
import Part # type: ignore

from . import core
from .i18n import translate as _

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icons")

GOLD = (1.0, 0.84, 0.0)
GOLD_EDGE = (0.62, 0.50, 0.0)
PLANE_FACE = (0.204, 0.659, 0.325)
PLANE_EDGE = (0.078, 0.373, 0.227)


def _add_property(obj, prop_type, name, group, doc, default=None):
    """Add the property only when it does not exist yet, to avoid redefinition."""
    if name in obj.PropertiesList:
        return
    obj.addProperty(prop_type, name, group, doc)
    if default is not None:
        setattr(obj, name, default)


# ----------------------------------------------------------------------
# Gold wire object
# ----------------------------------------------------------------------
class WireBondFeature:
    """Parametric gold wire (wire bond) object."""

    def __init__(self, obj):
        obj.Proxy = self
        _add_property(obj, "App::PropertyLinkSub", "Face1", "WireBond",
                      _("First plane (Face)"))
        _add_property(obj, "App::PropertyLinkSub", "Face2", "WireBond",
                      _("Second plane (Face)"))
        _add_property(obj, "App::PropertyLength", "WireDiameter", "WireBond",
                      _("Wire diameter (default 20 um)"),
                      core.DEFAULT_WIRE_DIAMETER)
        # The loop shape is a list of (position ratio, height) control points,
        # stored as a compact string like "0.4,0.2;0.6,0.18". One point is the
        # classic apex (it replaced the old Clearance + PeakRatio pair); extra
        # points turn the loop into a 4+N point spline. ``Label`` is the visible
        # face of the property; a StringList would not be editable as a table.
        _add_property(obj, "App::PropertyString", "LoopPoints", "WireBond",
                      _("Loop control points as ratio,height pairs in mm, "
                        "e.g. 0.4,0.2;0.6,0.18 - one point is the apex"),
                      core.format_loop_points(core.DEFAULT_LOOP_POINTS))
        # migrate a document saved before LoopPoints existed: fold the old
        # Clearance + PeakRatio into a single loop point, then drop the old
        # properties so the property editor no longer shows them.
        self._migrate_legacy_loop(obj)
        _add_property(obj, "App::PropertyAngle", "RiseAngle", "WireBond",
                      _("Angle at which the wire leaves the first pad, measured "
                        "from the horizontal plane: 0 deg is level and points at "
                        "the second pad, 90 deg is straight up"),
                      core.DEFAULT_RISE_ANGLE)
        _add_property(obj, "App::PropertyAngle", "FallAngle", "WireBond",
                      _("Angle at which the wire reaches the second pad, "
                        "measured from the horizontal plane: 0 deg is level and "
                        "points at the first pad, 90 deg is straight up"),
                      core.DEFAULT_FALL_ANGLE)
        _add_property(obj, "App::PropertyBool", "MakeSolid", "WireBond",
                      _("Create the gold wire solid (slower for very small "
                        "diameters)"), False)
        _add_property(obj, "App::PropertyBool", "ShowCentreline", "WireBond",
                      _("Also show the wire centreline"), True)
        # A PropertyEnumeration stores its choices when a *list* is assigned,
        # and its current value when a *string* is assigned - so the list has to
        # come first. Read the choices back with
        # ``obj.getEnumerationsOfProperty("StartBallMode")``;
        # ``list(obj.StartBallMode)`` would iterate the current value string.
        #
        # One selector per end: C1 (first bond point) and C2 (second bond point).
        # They replaced the earlier single ``BallMode`` plus the ``MakeBalls``
        # switch, which could not express "a ball here, a wedge there".
        _add_property(obj, "App::PropertyEnumeration", "StartBallMode", "WireBond",
                      _("Shape of the bump at the first bond point (C1)"))
        obj.StartBallMode = list(core.BUMP_MODES)
        obj.StartBallMode = core.BUMP_SPHERE
        _add_property(obj, "App::PropertyEnumeration", "EndBallMode", "WireBond",
                      _("Shape of the bump at the second bond point (C2)"))
        obj.EndBallMode = list(core.BUMP_MODES)
        obj.EndBallMode = core.BUMP_SPHERE
        _add_property(obj, "App::PropertyLength", "LeadDistance", "WireBond",
                      _("Distance from each pad to its entry/exit control point, "
                        "measured along the rise/fall ray (default 10 um)"),
                      core.DEFAULT_LEAD_DISTANCE)
        _add_property(obj, "App::PropertyLength", "BallDiameter", "WireBond",
                      _("Ball diameter (default 50 um); for a frustum it is "
                        "the bump height"),
                      core.DEFAULT_BALL_DIAMETER)
        # The property NAME is what the property editor shows (FreeCAD splits
        # the camel case into words), so it has to say "Frustum" too - a
        # description alone would leave the title reading "Ball Top Diameter".
        _add_property(obj, "App::PropertyLength", "FrustumTopDiameter", "WireBond",
                      _("Frustum: diameter of the end away from the pad"),
                      core.DEFAULT_FRUSTUM_TOP_DIAMETER)
        _add_property(obj, "App::PropertyLength", "FrustumBottomDiameter",
                      "WireBond",
                      _("Frustum: diameter of the end sitting on the pad"),
                      core.DEFAULT_FRUSTUM_BOTTOM_DIAMETER)
        _add_property(obj, "App::PropertyAngle", "PlaneRotation", "WireBond",
                      _("Rotation of the wire plane about the centroid line "
                        "(0 deg = coincident with the bisector plane)"),
                      core.DEFAULT_PLANE_ROTATION)

    @staticmethod
    def _migrate_legacy_loop(obj):
        """Fold the legacy Clearance / PeakRatio into ``LoopPoints``.

        Documents created before the loop-point list keep their ``Clearance`` and
        ``PeakRatio`` properties. The first time such an object is touched the two
        values become one loop point (a single point is exactly the old apex) and
        the old properties are removed, so old drawings keep their exact shape.
        """
        for name in ("Clearance", "PeakRatio"):
            if name not in obj.PropertiesList:
                continue
            try:
                height = float(obj.Clearance)
                ratio = float(obj.PeakRatio)
            except Exception:
                return
            obj.LoopPoints = core.format_loop_points([(ratio, height)])
            for legacy in ("Clearance", "PeakRatio"):
                try:
                    obj.removeProperty(legacy)
                except Exception:
                    pass
            return

    # -- geometry rebuild -------------------------------------------
    def execute(self, obj):
        try:
            face1 = self._resolve_face(obj, "Face1")
            face2 = self._resolve_face(obj, "Face2")
        except core.WireBondError:
            raise
        except Exception as exc:  # e.g. the referenced object was deleted
            raise core.WireBondError(
                _("Cannot read the selected faces: {}").format(exc)
            )

        result = core.compute_from_faces(
            face1,
            face2,
            wire_diameter=float(obj.WireDiameter),
            loop_points=getattr(obj, "LoopPoints",
                                core.format_loop_points(core.DEFAULT_LOOP_POINTS)),
            rise_angle=obj.RiseAngle.getValueAs("deg"),
            fall_angle=obj.FallAngle.getValueAs("deg"),
            make_solid=bool(obj.MakeSolid),
            ball_diameter=float(obj.BallDiameter),
            top_diameter=float(getattr(obj, "FrustumTopDiameter",
                                       obj.BallDiameter)),
            bottom_diameter=float(getattr(obj, "FrustumBottomDiameter",
                                          obj.BallDiameter)),
            start_ball_mode=getattr(obj, "StartBallMode", core.BUMP_SPHERE),
            end_ball_mode=getattr(obj, "EndBallMode", core.BUMP_SPHERE),
            lead_distance=float(getattr(obj, "LeadDistance",
                                        core.DEFAULT_LEAD_DISTANCE)),
            rotation_deg=obj.PlaneRotation.getValueAs("deg"),
        )

        shapes = []
        if result["solid"] is not None:
            shapes.append(result["solid"])
        if result["solid"] is None or obj.ShowCentreline:
            shapes.append(result["centre_line"])
        shapes.extend(result["balls"])  # the bond bumps at the two bond points

        obj.Shape = shapes[0] if len(shapes) == 1 else Part.makeCompound(shapes)

    @staticmethod
    def _resolve_face(obj, prop):
        """Return the referenced face, transformed to global coordinates (including App::Part parent transforms)."""
        ref = getattr(obj, prop)
        if not ref or ref[0] is None:
            raise core.WireBondError(
                _("{} has no face assigned.").format(prop)
            )
        target, sub = ref
        name = sub[0] if isinstance(sub, (list, tuple)) else sub
        return core.global_face(target, name)

    def onChanged(self, obj, prop):
        return

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def dumps(self):
        return None

    def loads(self, state):
        return


class ViewProviderWireBond:
    """Display style of the gold wire (gold coloured)."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        self.Object = vobj.Object
        try:
            vobj.ShapeColor = GOLD
            vobj.LineColor = GOLD_EDGE
            vobj.LineWidth = 2.0
            vobj.PointSize = 2.0
        except Exception:
            pass

    def getIcon(self):
        return os.path.join(ICON_DIR, "WireBond_Create.svg")

    def updateData(self, obj, prop):
        return

    def onChanged(self, vobj, prop):
        return

    def getDisplayModes(self, obj):
        return ["Flat Lines", "Shaded", "Wireframe", "Points"]

    def getDefaultDisplayMode(self):
        return "Flat Lines"

    def setDisplayMode(self, mode):
        return mode

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def dumps(self):
        return None

    def loads(self, state):
        return


# ----------------------------------------------------------------------
# Bisector plane object
# ----------------------------------------------------------------------
class BisectorPlaneFeature:
    """Bisector plane built from two faces (display / reference only)."""

    def __init__(self, obj):
        obj.Proxy = self
        _add_property(obj, "App::PropertyLinkSub", "Face1", "Plane",
                      _("First plane (Face)"))
        _add_property(obj, "App::PropertyLinkSub", "Face2", "Plane",
                      _("Second plane (Face)"))
        _add_property(obj, "App::PropertyLength", "Margin", "Plane",
                      _("Margin of the rectangle beyond both ends of the "
                        "centroid line"), core.DEFAULT_PLANE_MARGIN)
        _add_property(obj, "App::PropertyFloat", "WidthFactor", "Plane",
                      _("Rectangle half width = centroid distance x this "
                        "factor"), 0.35)
        _add_property(obj, "App::PropertyAngle", "PlaneRotation", "Plane",
                      _("Rotation of the wire plane about the centroid line "
                        "(0 deg = coincident with the bisector plane)"),
                      core.DEFAULT_PLANE_ROTATION)

    def execute(self, obj):
        face1 = WireBondFeature._resolve_face(obj, "Face1")
        face2 = WireBondFeature._resolve_face(obj, "Face2")
        c1, n1 = core.face_centre_and_normal(face1)
        c2, n2 = core.face_centre_and_normal(face2)
        frame = core.make_frame(
            c1, n1, c2, n2, rotation_deg=obj.PlaneRotation.getValueAs("deg")
        )
        obj.Shape = core.plane_face(
            frame, margin=float(obj.Margin), width_factor=float(obj.WidthFactor)
        )

    def onChanged(self, obj, prop):
        return

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def dumps(self):
        return None

    def loads(self, state):
        return


class ViewProviderBisectorPlane:
    """Display style of the bisector plane (semi-transparent green)."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        self.Object = vobj.Object
        try:
            vobj.ShapeColor = PLANE_FACE
            vobj.LineColor = PLANE_EDGE
            vobj.Transparency = 70
            vobj.LineWidth = 1.0
        except Exception:
            pass

    def getIcon(self):
        return os.path.join(ICON_DIR, "WireBond_Plane.svg")

    def updateData(self, obj, prop):
        return

    def onChanged(self, vobj, prop):
        return

    def getDisplayModes(self, obj):
        return ["Flat Lines", "Shaded", "Wireframe"]

    def getDefaultDisplayMode(self):
        return "Flat Lines"

    def setDisplayMode(self, mode):
        return mode

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def dumps(self):
        return None

    def loads(self, state):
        return

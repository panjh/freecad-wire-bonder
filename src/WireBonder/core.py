# -*- coding: utf-8 -*-
"""Wire bonding geometry core.

This module only depends on FreeCAD / Part and has no GUI dependency, so it can
be driven from the command panel as well as from the console or test scripts.

Construction rules
------------------
Given two selected faces F1 and F2:

1. take the centroids C1, C2 and the connecting direction ``d = normalize(C2 - C1)``;
2. take the normals n1, n2, first align them to the same hemisphere (flip n2 when
   the angle exceeds 90 degrees), then take the bisector ``b = normalize(n1 + n2)``;
3. the target plane P is spanned by ``d`` and ``b`` and passes through C1 and C2;
4. build a local frame inside P: the x axis along ``d``, the y axis as the
   orthogonal component of ``b`` within P, the z axis as the plane normal ``x x y``;
5. generate a wire loop inside P connecting C1 and C2; the height of the loop
   peak above the connecting line is the "clearance";
6. sweep a circle of diameter ``wire_diameter`` along that curve to obtain the
   gold wire solid.
"""

import math
from collections import namedtuple

import FreeCAD as App # type: ignore
import Part # type: ignore
from FreeCAD import Vector # type: ignore

from .i18n import translate as _

__all__ = [
    "WireBondError",
    "Frame",
    "face_from_subname",
    "face_global_transform",
    "global_face",
    "face_centre_and_normal",
    "make_frame",
    "loop_profile",
    "to_world",
    "build_centreline",
    "sweep_wire",
    "bond_balls",
    "plane_face",
    "compute_from_faces",
]


class WireBondError(Exception):
    """Raised when the geometry construction fails; the message is user facing."""


# ----------------------------------------------------------------------
# Default parameters (in mm)
# ----------------------------------------------------------------------
DEFAULT_WIRE_DIAMETER = 0.02   # 20 um, typical gold wire diameter
DEFAULT_CLEARANCE = 0.5        # clearance 500 um (loop peak above the centroid line)
DEFAULT_PEAK_RATIO = 0.42      # loop peak position as a ratio of the centroid distance
DEFAULT_RISE_RATIO = 0.60      # height ratio of the steep rise point near the start
DEFAULT_FALL_RATIO = 0.20      # height ratio of the landing point near the end
DEFAULT_BALL_DIAMETER = 0.05   # bond ball diameter 50 um (about 2.5x the wire diameter)
DEFAULT_PLANE_ROTATION = 0.0   # wire plane rotation about the centroid line (deg), 0 = coincident
DEFAULT_PLANE_MARGIN = 2.0     # visual margin of the helper plane rectangle (mm)

Frame = namedtuple("Frame", "origin xdir ydir zdir length")


# ----------------------------------------------------------------------
# Basic helpers
# ----------------------------------------------------------------------
def _normalize(vec, what):
    """Normalise a vector; ``what`` is an English msgid localised by i18n."""
    if vec.Length < 1e-12:
        raise WireBondError(_("{} has zero length; cannot determine its direction.").format(what))
    return Vector(vec.x, vec.y, vec.z) / vec.Length


def face_from_subname(shape, subname):
    """Return the face denoted by a GUI sub-element name such as ``Face3``."""
    if not subname.startswith("Face"):
        raise WireBondError(
            _("Selected sub-element {} is not a face; please select exactly "
              "two faces.").format(subname)
        )
    try:
        index = int(subname[4:]) - 1
    except ValueError:
        raise WireBondError(
            _("Cannot parse sub-element name: {}").format(subname)
        )

    faces = shape.Faces
    if index < 0 or index >= len(faces):
        raise WireBondError(_("Face index out of range: {}").format(subname))
    return faces[index]


def face_global_transform(obj):
    """Return the transform needed to lift ``obj.Shape`` into global coordinates.

    ``obj.Shape`` already contains the object's **own** Placement but **not the
    parent container** (``App::Part`` / ``PartDesign::Body`` ...) Placement. For
    parts inside an assembly, using ``face.CenterOfMass`` directly yields a
    position offset from the global assembly and the wire is drawn outside the
    model. This returns ``getGlobalPlacement() * Placement^-1``, i.e. the part
    contributed by the parent chain; ``None`` when no transform is needed.
    """
    try:
        return obj.getGlobalPlacement().multiply(obj.Placement.inverse())
    except Exception:
        return None


def global_face(obj, subname):
    """Return the face ``subname`` of ``obj``, transformed to **global** coordinates.

    All geometry computations should use this function (rather than
    ``face_from_subname``), otherwise the wire position of parts inside an
    assembly is wrong. Returns the face unchanged when there is no parent transform.
    """
    face = face_from_subname(obj.Shape, subname)
    extra = face_global_transform(obj)
    if extra is None:
        return face
    try:
        if extra.isIdentity():
            return face
    except Exception:
        pass
    return face.transformed(extra.toMatrix())


def face_centre_and_normal(face):
    """Return the face centroid and normal (normal oriented by the face, normalised).

    Note: the face passed in should already be in global coordinates (obtain it
    with :func:`global_face`).
    """
    centre = face.CenterOfMass
    try:
        normal = face.normalAt(0.5, 0.5)
    except Exception:  # degenerate case: fall back to the surface axis
        try:
            normal = face.Surface.Axis
        except Exception:
            raise WireBondError(_("Cannot obtain the face normal."))
    return centre, _normalize(normal, _("face normal"))


# ----------------------------------------------------------------------
# Bisector plane construction
# ----------------------------------------------------------------------
def make_frame(c1, n1, c2, n2, rotation_deg=DEFAULT_PLANE_ROTATION):
    """Build the local frame of the wire plane (bisector plane).

    Returns ``Frame(origin, xdir, ydir, zdir, length)``:
        origin = C1
        xdir   = centroid line direction
        ydir   = bisector of the two centroid normals (orthogonal component in plane)
        zdir   = plane normal = xdir x ydir
        length = |C2 - C1|

    ``rotation_deg`` is the **rotation of the wire plane about the centroid
    line** (in degrees): ``0`` means the wire plane is exactly coincident with
    the bisector plane; a non-zero value rotates the local y/z axes about the x
    axis by that angle, so the wire enters and leaves diagonally and the loop
    peak direction changes accordingly.
    """
    c1 = Vector(c1.x, c1.y, c1.z)
    c2 = Vector(c2.x, c2.y, c2.z)
    n1 = Vector(n1.x, n1.y, n1.z)
    n2 = Vector(n2.x, n2.y, n2.z)

    length = (c2 - c1).Length
    if length < 1e-9:
        raise WireBondError(
            _("The two face centroids coincide; cannot determine the "
              "connecting direction.")
        )

    xdir = _normalize(c2 - c1, _("centroid line"))

    # align both normals to the same hemisphere
    if float(n1.dot(n2)) < 0.0:
        n2 = Vector(-n2.x, -n2.y, -n2.z)

    bisector = n1 + n2
    if bisector.Length < 1e-9:
        raise WireBondError(
            _("The two face normals are 180 degrees apart, so no bisector "
              "exists; please select two faces with a consistent orientation.")
        )

    # keep the component of the bisector perpendicular to the line
    # (Gram-Schmidt) so that the y axis lies inside the plane
    ydir_raw = bisector - xdir * float(bisector.dot(xdir))
    if ydir_raw.Length < 1e-9 * max(1.0, bisector.Length):
        raise WireBondError(
            _("The centroid line is parallel to the normal bisector, so the "
              "plane is not unique; please select two faces whose normals "
              "differ in direction.")
        )
    ydir = _normalize(ydir_raw, _("normal bisector"))
    zdir = _normalize(xdir.cross(ydir), _("plane normal"))

    # rotate the wire plane about the centroid line (x axis):
    # 0 degrees means fully coincident with the bisector plane
    rotation = float(rotation_deg or 0.0)
    if abs(rotation) > 1e-12:
        rot = App.Rotation(xdir, rotation)
        ydir = _normalize(rot.multVec(ydir), _("rotated Y axis"))
        zdir = _normalize(rot.multVec(zdir), _("rotated plane normal"))

    return Frame(c1, xdir, ydir, zdir, length)


# ----------------------------------------------------------------------
# Wire loop profile
# ----------------------------------------------------------------------
def loop_profile(length, clearance, peak_ratio=DEFAULT_PEAK_RATIO,
                 rise_ratio=DEFAULT_RISE_RATIO, fall_ratio=DEFAULT_FALL_RATIO):
    """Return the wire loop control points ``[(u, v), ...]`` in plane-local coordinates.

    ``u`` runs along the centroid line (0 -> length) and ``v`` is the height
    above that line (0 -> clearance). The shape mimics the trajectory of a wire
    bonder: steep rise after leaving the pad -> loop peak -> gentle descent.
    """
    length = float(length)
    height = float(clearance)
    if length <= 0.0:
        raise WireBondError(_("The centroid distance must be greater than zero."))
    if height < 0.0:
        raise WireBondError(_("Clearance must not be negative."))

    ratio = min(max(float(peak_ratio), 0.05), 0.95)
    peak_u = length * ratio
    tail = length - peak_u

    return [
        (0.0, 0.0),
        (0.12 * peak_u, min(1.0, rise_ratio) * height),   # leaving the pad: steep rise
        (0.50 * peak_u, 0.92 * height),
        (peak_u, height),                                  # loop peak
        (peak_u + 0.35 * tail, 0.88 * height),
        (peak_u + 0.70 * tail, 0.50 * height),
        (peak_u + 0.92 * tail, min(0.6, fall_ratio * 2.0) * height),
        (length, 0.0),
    ]


def to_world(frame, points2d):
    """Map the local 2D control points into 3D space."""
    return [frame.origin + frame.xdir * u + frame.ydir * v for (u, v) in points2d]


def build_centreline(points3d):
    """Build an interpolated spline from the control points; returns the centreline (Part.Wire)."""
    curve = Part.BSplineCurve()
    curve.interpolate([Vector(p.x, p.y, p.z) for p in points3d])
    return Part.Wire([curve.toShape()])


def sweep_wire(path_wire, diameter):
    """Sweep a circle of the given diameter along the path; returns the wire solid (Part.Solid)."""
    diameter = float(diameter)
    if diameter <= 0.0:
        raise WireBondError(_("Wire diameter must be greater than zero."))

    edge = path_wire.Edges[0]
    start = edge.valueAt(edge.FirstParameter)
    tangent = _normalize(
        edge.tangentAt(edge.FirstParameter), _("path start tangent")
    )

    profile = Part.Wire([Part.makeCircle(diameter / 2.0, start, tangent)])
    solid = path_wire.makePipeShell([profile], True, False)

    # OCCT sometimes returns an inward facing shell (negative volume); flip it
    volume = solid.Volume
    if volume < 0.0:
        fixed = solid.copy()
        fixed.reverse()
        solid = fixed
    if not solid.isValid():
        App.Console.PrintWarning(
            _("WireBond: the swept result is not a valid solid; please check "
              "whether the wire diameter is too small.\n")
        )
    return solid


def bond_balls(centre1, centre2, diameter=DEFAULT_BALL_DIAMETER):
    """Create one bond ball at each centroid, representing the two bond points."""
    diameter = float(diameter)
    if diameter <= 0.0:
        raise WireBondError(_("Ball diameter must be greater than zero."))

    radius = diameter / 2.0
    balls = []
    for centre in (centre1, centre2):
        balls.append(Part.makeSphere(radius, Vector(centre.x, centre.y, centre.z)))
    return balls


def plane_face(frame, margin=DEFAULT_PLANE_MARGIN, width_factor=0.35):
    """Visual rectangle of the bisector plane (helper plane, shown on its own).

    The rectangle extends ``margin`` beyond both ends of the connecting line,
    and its width is a fraction of the line length.
    """
    half_w = max(frame.length * float(width_factor), 1e-6) + float(margin)
    u0, u1 = -abs(float(margin)), frame.length + abs(float(margin))
    v0, v1 = -half_w, half_w
    pts = [
        frame.origin + frame.xdir * u + frame.ydir * v
        for (u, v) in ((u0, v0), (u1, v0), (u1, v1), (u0, v1), (u0, v0))
    ]
    return Part.Face(Part.makePolygon(pts))


# ----------------------------------------------------------------------
# One-shot interface (used by the command, scripts and tests)
# ----------------------------------------------------------------------
def compute_from_faces(face1, face2, wire_diameter=DEFAULT_WIRE_DIAMETER,
                       clearance=DEFAULT_CLEARANCE,
                       peak_ratio=DEFAULT_PEAK_RATIO,
                       rise_ratio=DEFAULT_RISE_RATIO,
                       fall_ratio=DEFAULT_FALL_RATIO,
                       make_solid=True,
                       make_balls=False,
                       ball_diameter=DEFAULT_BALL_DIAMETER,
                       rotation_deg=DEFAULT_PLANE_ROTATION):
    """Compute the bisector plane, the gold wire and the bond balls from two faces.

    ``rotation_deg``: rotation of the wire plane about the centroid line (deg),
    default 0.

    Returns a dict with frame / centre_line / solid / balls / plane plus the
    intermediate centroids and normals.
    """
    c1, n1 = face_centre_and_normal(face1)
    c2, n2 = face_centre_and_normal(face2)
    frame = make_frame(c1, n1, c2, n2, rotation_deg=rotation_deg)

    points2d = loop_profile(frame.length, clearance, peak_ratio,
                            rise_ratio, fall_ratio)
    points3d = to_world(frame, points2d)
    centre_line = build_centreline(points3d)

    solid = None
    if make_solid:
        solid = sweep_wire(centre_line, wire_diameter)

    balls = bond_balls(c1, c2, ball_diameter) if make_balls else []

    return {
        "frame": frame,
        "centre1": c1,
        "centre2": c2,
        "normal1": n1,
        "normal2": n2,
        "points2d": points2d,
        "points3d": points3d,
        "centre_line": centre_line,
        "solid": solid,
        "balls": balls,
        "plane": plane_face(frame),
    }

# -*- coding: utf-8 -*-
"""WireBonder: a wire bonding helper addon for FreeCAD.

Select any two faces and the addon will
  * take the line connecting the two face centroids,
  * take the bisector of the two centroid normals,
  * span the "bisector plane" from those two directions,
  * generate a wire loop between the two centroids inside that plane and sweep
    it with the configured gold wire diameter to obtain a solid.

The wire diameter and the clearance stay fully parametric.
"""

__version__ = "0.12.0"
__all__ = [
    "core",
    "features",
    "taskpanel",
    "commands",
    "i18n",
    "language_monitor",
    "settings",
]

"""Recover Meshy's automatic recentering from shared texture coordinates."""
import numpy as np
from mathutils import Vector


def uv_world_points(mesh):
    points = {}
    layer = mesh.data.uv_layers.active
    if not layer:
        raise RuntimeError('Textured input is required for native alignment')
    for loop in mesh.data.loops:
        key = tuple(round(value, 5) for value in layer.data[loop.index].uv)
        points[key] = tuple(mesh.matrix_world@mesh.data.vertices[loop.vertex_index].co)
    return points


def recover_translation(reference, mesh):
    returned = uv_world_points(mesh)
    common = reference.keys() & returned.keys()
    if len(common) < 100:
        raise RuntimeError(f'Insufficient shared UV samples: {len(common)}')
    differences = np.array([reference[key] for key in common])-np.array([returned[key] for key in common])
    translation = np.median(differences, axis=0)
    error = np.linalg.norm(differences-translation, axis=1)
    # UV seams and cut-cap UVs can alias, so verify the dominant correspondence.
    inliers = error < .002
    if np.mean(inliers) < .75:
        raise RuntimeError(f'Native model is not a translated copy: {np.mean(inliers):.1%} inliers')
    translation = np.median(differences[inliers], axis=0)
    return Vector(translation), {'translation': list(translation), 'shared_uv_samples': len(common),
        'inlier_fraction': float(np.mean(inliers)), 'median_residual_m': float(np.median(error))}

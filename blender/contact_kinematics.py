"""Two-segment contact solve, in armature space; no bone stretching."""
import math
import bpy
from mathutils import Matrix, Vector


def smooth(a, b, value):
    t = max(0, min(1, (value-a)/(b-a)))
    return t*t*(3-2*t)


def solve_chain(rig, upper_name, lower_name, tip_name, target, pole, orientation=None):
    upper, lower, tip = [rig.pose.bones[n] for n in (upper_name, lower_name, tip_name)]
    root = upper.head.copy()
    l1 = (lower.bone.head_local-upper.bone.head_local).length
    l2 = (tip.bone.head_local-lower.bone.head_local).length
    delta = target-root
    distance = max(abs(l1-l2)+1e-5, min(delta.length, l1+l2-1e-5))
    direction = delta.normalized()
    projected = pole-root-direction*(pole-root).dot(direction)
    if projected.length < 1e-6:
        projected = direction.cross(Vector((1, 0, 0)))
    bend = projected.normalized()
    along = (l1*l1-l2*l2+distance*distance)/(2*distance)
    knee = root+direction*along+bend*math.sqrt(max(0, l1*l1-along*along))
    reached = root+direction*distance
    for pb, start, end, rest_end in ((upper, root, knee, lower.bone.head_local),
                                    (lower, knee, reached, tip.bone.head_local)):
        rest_direction = rest_end-pb.bone.head_local
        rotation = rest_direction.rotation_difference(end-start)
        matrix = rotation.to_matrix().to_4x4()@pb.bone.matrix_local
        matrix.translation = start
        pb.matrix = matrix
        bpy.context.view_layer.update()
    if orientation is not None:
        tip.matrix = Matrix.LocRotScale(reached, orientation, Vector((1, 1, 1)))
        bpy.context.view_layer.update()
    return (tip.head-target).length


def floor_cycle(progress, offset, stride, lift, duty=.76):
    phase = (progress+offset)%1
    if phase < duty:
        return -stride*.5+stride*phase/duty, 0.0, True
    swing = (phase-duty)/(1-duty)
    return stride*.5-stride*smooth(0, 1, swing), lift*math.sin(math.pi*swing)**2, False

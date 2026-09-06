"""Calibrate approved scene masters and export two platform derivatives."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_meshy_sample import bounds, repair_normals, reduce_triangles, select_meshes, triangle_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", choices=("board_main", "camp_red", "camp_black", "watchtower"), required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    root = Path(__file__).resolve().parents[1]
    base = root / "assets/generated/meshy/scene" / args.asset
    source, output = base / "geometry/v1/model.glb", base / "runtime/v1"
    assert not output.exists(), "Use a fresh output directory"
    output.mkdir(parents=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for obj in objects:
        matrix = obj.matrix_world.copy()
        obj.data = obj.data.copy()
        obj.parent = None
        obj.data.transform(matrix)
        obj.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    low, high = bounds(objects)
    dimensions = high-low
    report = {"asset": args.asset, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "source_unchanged": True, "source_triangles": triangle_count(objects), "files": {}}
    if args.asset == "board_main":
        # The broad API slab has a shallow wavy trench. Compress the central
        # region to fit entirely between ranks 4/5, preserving the outer frame.
        scale = Matrix.Diagonal((10.25/dimensions.x, 11.35/dimensions.y, 2.0, 1))
        center = Vector(((low.x+high.x)/2, (low.y+high.y)/2, 0))
        transform = Matrix.Translation((0,0,.25-.18085*2)) @ scale @ Matrix.Translation(-center)
        for obj in objects:
            obj.data.transform(transform)
            xyz = np.empty(len(obj.data.vertices)*3, np.float32)
            obj.data.vertices.foreach_get("co", xyz)
            xyz = xyz.reshape(-1,3)
            distance = np.abs(xyz[:,1])
            xyz[:,1] = np.sign(xyz[:,1])*np.where(distance<=1.1, distance*.40, .44+(distance-1.1)*(5.675-.44)/(5.675-1.1))
            inside = (np.abs(xyz[:,0]) < 4.76) & (np.abs(xyz[:,1]) < 5.25)
            field = inside & (np.abs(xyz[:,1]) >= .46) & (xyz[:,2] > .19)
            xyz[field,2] = .25
            obj.data.vertices.foreach_set("co", xyz.ravel())
            obj.data.update()
        report["calibration"] = "10.25 x 11.35 slab, flat fields at Y=.25, center trench narrowed between ranks 4 and 5; UVs retained"
    else:
        width, height = (1.3,2.65) if args.asset == "watchtower" else (2.05,1.75)
        scale = min(width/max(dimensions.x,dimensions.y), height/dimensions.z)
        center = Vector(((low.x+high.x)/2, (low.y+high.y)/2, low.z))
        transform = Matrix.Scale(scale,4) @ Matrix.Translation(-center)
        for obj in objects:
            obj.data.transform(transform)
        report["normalization_scale"] = scale
    bpy.context.view_layer.update()
    images = [image for image in bpy.data.images if image.type=="IMAGE" and image.size[0]>0]
    report["source_images"] = [{"name": image.name, "size": list(image.size)} for image in images]
    for image in images:
        if not image.packed_file: image.pack()
    select_meshes(objects)
    bpy.ops.wm.save_as_mainfile(filepath=str(output/(args.asset+"_source.blend")), compress=True)
    repair_normals(objects)
    for tier, target, pixels in (("desktop",80000 if args.asset=="board_main" else 30000,4096),
                                 ("mobile",30000 if args.asset=="board_main" else 12000,2048)):
        reduce_triangles(objects,target)
        for image in images:
            w,h=image.size
            if max(w,h)>pixels:
                image.scale(round(w*pixels/max(w,h)),round(h*pixels/max(w,h))); image.pack()
        select_meshes(objects)
        destination=output/f"{args.asset}_{tier}.glb"
        bpy.ops.export_scene.gltf(filepath=str(destination),export_format="GLB",use_selection=True,
            export_yup=True,export_image_format="WEBP",export_image_quality=95,export_materials="EXPORT")
        lo,hi=bounds(objects)
        item={"file":destination.name,"bytes":destination.stat().st_size,"sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),
              "triangles":triangle_count(objects),"bounds":{"min":list(lo),"max":list(hi)},
              "images":[{"name":image.name,"size":list(image.size)}for image in images]}
        if args.asset=="board_main":
            trees=[BVHTree.FromObject(obj,bpy.context.evaluated_depsgraph_get()) for obj in objects]
            heights=[]
            for rank in range(10):
                for file in range(9):
                    ray=Vector(((file-4)*1.05,-(rank-4.5)*1.05,3))
                    hits=[tree.ray_cast(ray,Vector((0,0,-1)))[0] for tree in trees]
                    hits=[hit.z for hit in hits if hit is not None]
                    assert hits,"Uncovered grid point"
                    heights.append(max(hits))
            item["grid_heights"] = heights
            item["maximum_grid_height_error"] = max(abs(h-.25) for h in heights)
            assert item["maximum_grid_height_error"] < .008,"Non-flat playing field"
        report["files"][tier]=item
        print("SCENE_EXPORTED",args.asset,tier,item["triangles"],item["bytes"],flush=True)
    (output/"runtime.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")


if __name__=="__main__": main()

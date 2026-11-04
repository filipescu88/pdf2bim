"""Inspect Poly Haven foliage FBX files in Blender 5.1: mesh names, vertex counts, bounding boxes, and material slots."""
import os
import bpy

fol_dir = "C:/Users/filip/pdf2bim_remote/foliage"
for fn in sorted(os.listdir(fol_dir)):
    if not fn.endswith(".fbx"):
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = os.path.join(fol_dir, fn)
    bpy.ops.import_scene.fbx(filepath=p)
    print(f"=== {fn} ===")
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            me = obj.data
            mats = [m.name if m else "None" for m in me.materials]
            zs = [ (obj.matrix_world @ v.co).z for v in me.vertices ] if me.vertices else [0.0]
            xs = [ (obj.matrix_world @ v.co).x for v in me.vertices ] if me.vertices else [0.0]
            ys = [ (obj.matrix_world @ v.co).y for v in me.vertices ] if me.vertices else [0.0]
            print(
                f"  MESH {obj.name:28s} verts={len(me.vertices):7d} polys={len(me.polygons):7d} "
                f"mats={mats} X=[{min(xs):.2f}..{max(xs):.2f}] Y=[{min(ys):.2f}..{max(ys):.2f}] Z=[{min(zs):.2f}..{max(zs):.2f}]"
            )

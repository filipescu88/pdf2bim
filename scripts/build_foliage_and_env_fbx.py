"""Build optimized 3D Foliage, Garden Hardscape (Terrace + Gravel Strip), and 360 SkyDome FBX in Blender 5.1."""
import os
import math
import random
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

fol_dir = "C:/Users/filip/pdf2bim_remote/foliage"
out_fbx = os.path.join(fol_dir, "foliage_and_env.fbx")

bpy.ops.wm.read_factory_settings(use_empty=True)
main_col = bpy.context.scene.collection


def get_or_make_mat(name, color_rgb=(0.5, 0.5, 0.5)):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*color_rgb, 1.0)
    return m


def import_fbx_objects(filename):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(fol_dir, filename))
    after = set(bpy.data.objects)
    new_objs = [o for o in (after - before) if o.type == "MESH"]
    non_mesh = [o for o in (after - before) if o.type != "MESH"]
    for o in new_objs:
        bpy.context.view_layer.objects.active = o
        o.parent = None
    bpy.ops.object.select_all(action="DESELECT")
    for o in new_objs:
        o.select_set(True)
    if new_objs:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in non_mesh:
        bpy.data.objects.remove(o, do_unlink=True)
    return new_objs


def recenter_mesh_bottom(obj):
    me = obj.data
    if not me.vertices:
        return
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    zmin = min(zs)
    for v in me.vertices:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= zmin
    me.update()


# ---------------------------------------------------------------------------
# 1. Load & optimize SM_Boulder_01 (from boulder_01_LOD3)
# ---------------------------------------------------------------------------
boulder_objs = import_fbx_objects("boulder_01_1k.fbx")
boulder_lod3 = None
for o in boulder_objs:
    if "LOD3" in o.name:
        boulder_lod3 = o
    else:
        bpy.data.objects.remove(o, do_unlink=True)
if boulder_lod3:
    boulder_lod3.name = "SM_Boulder_01"
    boulder_lod3.data.name = "SM_Boulder_01"
    recenter_mesh_bottom(boulder_lod3)
    boulder_lod3.data.materials.clear()
    boulder_lod3.data.materials.append(get_or_make_mat("M_Foliage_Boulder", (0.45, 0.44, 0.42)))
    print("Prepared SM_Boulder_01 polys=", len(boulder_lod3.data.polygons))


# ---------------------------------------------------------------------------
# 2. Load & build SM_Grass_Patch_3D (2.6m x 2.6m dense 3D meadow clumps & tufts)
# ---------------------------------------------------------------------------
grass_objs = import_fbx_objects("grass_medium_01_1k.fbx")
tuft_templates = []
for o in grass_objs:
    if any(k in o.name for k in ("large_a", "large_b", "large_c", "mid_a", "mid_b", "mid_c", "small_a", "small_b")):
        recenter_mesh_bottom(o)
        tuft_templates.append(o)
    else:
        bpy.data.objects.remove(o, do_unlink=True)

rng = random.Random(101)
bm_grass = bmesh.new()
for idx in range(34):
    tpl = tuft_templates[idx % len(tuft_templates)]
    bm_tmp = bmesh.new()
    bm_tmp.from_mesh(tpl.data)
    angle = rng.uniform(0.0, math.tau)
    sc_xy = rng.uniform(1.30, 1.85)
    sc_z = rng.uniform(0.95, 1.45)
    ox = rng.uniform(-1.15, 1.15)
    oy = rng.uniform(-1.15, 1.15)
    rot_mat = Euler((0.0, 0.0, angle), "XYZ").to_matrix().to_4x4()
    scale_mat = Matrix.Diagonal((sc_xy, sc_xy, sc_z, 1.0))
    xform = Matrix.Translation((ox, oy, 0.0)) @ rot_mat @ scale_mat
    bmesh.ops.transform(bm_tmp, matrix=xform, verts=bm_tmp.verts)
    me_tmp = bpy.data.meshes.new("_tmp_g")
    bm_tmp.to_mesh(me_tmp)
    bm_tmp.free()
    bm_grass.from_mesh(me_tmp)
    bpy.data.meshes.remove(me_tmp)

for o in tuft_templates:
    bpy.data.objects.remove(o, do_unlink=True)

me_grass_patch = bpy.data.meshes.new("SM_Grass_Patch_3D")
bm_grass.to_mesh(me_grass_patch)
bm_grass.free()
obj_grass_patch = bpy.data.objects.new("SM_Grass_Patch_3D", me_grass_patch)
main_col.objects.link(obj_grass_patch)
me_grass_patch.materials.append(get_or_make_mat("M_Foliage_Grass_01", (0.30, 0.48, 0.18)))
print("Prepared SM_Grass_Patch_3D polys=", len(me_grass_patch.polygons))


# ---------------------------------------------------------------------------
# 3. Load & build SM_Shrub_02_A, SM_Shrub_02_B, and SM_Hedge_Row_4m
# ---------------------------------------------------------------------------
shrub2_objs = sorted(import_fbx_objects("shrub_02_1k.fbx"), key=lambda x: x.name)
for o in shrub2_objs:
    recenter_mesh_bottom(o)

# Build SM_Hedge_Row_4m from 5 overlapping rotated bushes along X in [-1.8..+1.8m]
bm_hedge = bmesh.new()
hedge_offsets = [(-1.60, -0.06, 0.2, 1.12), (-0.80, 0.07, 1.7, 1.18), (0.0, -0.05, 3.4, 1.15), (0.80, 0.06, 4.9, 1.20), (1.60, -0.04, 0.9, 1.14)]
for i, (hx, hy, hang, hsc) in enumerate(hedge_offsets):
    tpl = shrub2_objs[i % len(shrub2_objs)]
    bm_tmp = bmesh.new()
    bm_tmp.from_mesh(tpl.data)
    rot_m = Euler((0.0, 0.0, hang), "XYZ").to_matrix().to_4x4()
    sc_m = Matrix.Diagonal((hsc, hsc, hsc * 1.05, 1.0))
    bmesh.ops.transform(bm_tmp, matrix=Matrix.Translation((hx, hy, 0.0)) @ rot_m @ sc_m, verts=bm_tmp.verts)
    me_tmp = bpy.data.meshes.new("_tmp_h")
    bm_tmp.to_mesh(me_tmp)
    bm_tmp.free()
    bm_hedge.from_mesh(me_tmp)
    bpy.data.meshes.remove(me_tmp)

me_hedge = bpy.data.meshes.new("SM_Hedge_Row_4m")
bm_hedge.to_mesh(me_hedge)
bm_hedge.free()
obj_hedge = bpy.data.objects.new("SM_Hedge_Row_4m", me_hedge)
main_col.objects.link(obj_hedge)
mat_shrub2 = get_or_make_mat("M_Foliage_Shrub_02", (0.26, 0.42, 0.18))
me_hedge.materials.append(mat_shrub2)
print("Prepared SM_Hedge_Row_4m polys=", len(me_hedge.polygons))

# Keep 2 individual shrub_02 variants: SM_Shrub_02_A and SM_Shrub_02_B
for idx, o in enumerate(shrub2_objs):
    if idx == 0:
        o.name = "SM_Shrub_02_A"
        o.data.name = "SM_Shrub_02_A"
        o.data.materials.clear()
        o.data.materials.append(mat_shrub2)
    elif idx == 2:
        o.name = "SM_Shrub_02_B"
        o.data.name = "SM_Shrub_02_B"
        o.data.materials.clear()
        o.data.materials.append(mat_shrub2)
    else:
        bpy.data.objects.remove(o, do_unlink=True)


# ---------------------------------------------------------------------------
# 4. Load & build SM_Shrub_01_Bush (from shrub_01_a..f)
# ---------------------------------------------------------------------------
shrub1_objs = import_fbx_objects("shrub_01_1k.fbx")
s1_parts = []
for o in shrub1_objs:
    if any(k in o.name for k in ("_a_", "_b_", "_c_", "_d_", "_e_", "_f_")):
        recenter_mesh_bottom(o)
        s1_parts.append(o)
    else:
        bpy.data.objects.remove(o, do_unlink=True)

bm_s1 = bmesh.new()
for i, p in enumerate(s1_parts):
    bm_tmp = bmesh.new()
    bm_tmp.from_mesh(p.data)
    ang = i * (math.tau / max(1, len(s1_parts)))
    rad = 0.14 if i > 0 else 0.0
    ox = math.cos(ang) * rad
    oy = math.sin(ang) * rad
    rot_m = Euler((0.08, 0.0, ang), "XYZ").to_matrix().to_4x4()
    sc_m = Matrix.Diagonal((2.2, 2.2, 2.3, 1.0))
    bmesh.ops.transform(bm_tmp, matrix=Matrix.Translation((ox, oy, 0.0)) @ rot_m @ sc_m, verts=bm_tmp.verts)
    me_tmp = bpy.data.meshes.new("_tmp_s1")
    bm_tmp.to_mesh(me_tmp)
    bm_tmp.free()
    bm_s1.from_mesh(me_tmp)
    bpy.data.meshes.remove(me_tmp)

for o in s1_parts:
    bpy.data.objects.remove(o, do_unlink=True)

me_s1 = bpy.data.meshes.new("SM_Shrub_01_Bush")
bm_s1.to_mesh(me_s1)
bm_s1.free()
obj_s1 = bpy.data.objects.new("SM_Shrub_01_Bush", me_s1)
main_col.objects.link(obj_s1)
me_s1.materials.append(get_or_make_mat("M_Foliage_Shrub_01", (0.34, 0.48, 0.22)))
print("Prepared SM_Shrub_01_Bush polys=", len(me_s1.polygons))


# ---------------------------------------------------------------------------
# 5. Load & optimize SM_Potted_Plant_01
# ---------------------------------------------------------------------------
pot_objs = import_fbx_objects("potted_plant_01_1k.fbx")
mat_pot = get_or_make_mat("M_Foliage_Pot", (0.45, 0.44, 0.42))
mat_pleaves = get_or_make_mat("M_Foliage_Plant_Leaves", (0.28, 0.45, 0.20))

for o in pot_objs:
    bpy.context.view_layer.objects.active = o
    if "pebbles" in o.name:
        mod = o.modifiers.new("Dec", "DECIMATE")
        mod.ratio = 0.08
        bpy.ops.object.modifier_apply(modifier=mod.name)
    elif "leaves" in o.name:
        # Keep every 3rd leaf island to preserve UVs cleanly
        bm = bmesh.new()
        bm.from_mesh(o.data)
        visited = set()
        to_del = []
        isl_idx = 0
        for f in bm.faces:
            if f in visited:
                continue
            comp = [f]
            visited.add(f)
            q = 0
            while q < len(comp):
                cur = comp[q]
                q += 1
                for v in cur.verts:
                    for nf in v.link_faces:
                        if nf not in visited:
                            visited.add(nf)
                            comp.append(nf)
            if isl_idx % 3 != 0:
                to_del.extend(comp)
            else:
                iverts = list({v for cf in comp for v in cf.verts})
                c = sum((v.co for v in iverts), Vector((0.0, 0.0, 0.0))) / len(iverts)
                for v in iverts:
                    v.co = c + (v.co - c) * 1.22
            isl_idx += 1
        if to_del:
            bmesh.ops.delete(bm, geom=to_del, context="FACES")
        bm.to_mesh(o.data)
        bm.free()
    o.data.materials.clear()
    if "leaves" in o.name:
        o.data.materials.append(mat_pleaves)
    else:
        o.data.materials.append(mat_pot)

bpy.ops.object.select_all(action="DESELECT")
for o in pot_objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = pot_objs[0]
bpy.ops.object.join()
obj_pot = bpy.context.active_object
obj_pot.name = "SM_Potted_Plant_01"
obj_pot.data.name = "SM_Potted_Plant_01"
recenter_mesh_bottom(obj_pot)
print("Prepared SM_Potted_Plant_01 polys=", len(obj_pot.data.polygons))


# ---------------------------------------------------------------------------
# 6. Load & optimize SM_Tree_Small_02 (preserving 100% leaf UVs via island thinning)
# ---------------------------------------------------------------------------
tree_objs = import_fbx_objects("tree_small_02_1k.fbx")
tree_obj = tree_objs[0]
tree_obj.name = "SM_Tree_Small_02"
tree_obj.data.name = "SM_Tree_Small_02"
recenter_mesh_bottom(tree_obj)

bm = bmesh.new()
bm.from_mesh(tree_obj.data)
leaf_mat_idx = next((i for i, m in enumerate(tree_obj.data.materials) if m and "leaves" in m.name), 1)
branch_mat_idx = next((i for i, m in enumerate(tree_obj.data.materials) if m and "branch" in m.name), 0)

# Copy UV_map_01 into UVMap for branch faces so all 3 slots use UVMap (TexCoord[0] in UE5)
if "UVMap" in bm.loops.layers.uv and "UV_map_01" in bm.loops.layers.uv:
    uv0 = bm.loops.layers.uv["UVMap"]
    uv1 = bm.loops.layers.uv["UV_map_01"]
    for f in bm.faces:
        if f.material_index == branch_mat_idx:
            for lp in f.loops:
                lp[uv0].uv = lp[uv1].uv
    bm.loops.layers.uv.remove(uv1)

visited = set()
to_del = []
isl_idx = 0
for f in bm.faces:
    if f.material_index != leaf_mat_idx or f in visited:
        continue
    comp = [f]
    visited.add(f)
    q = 0
    while q < len(comp):
        cur = comp[q]
        q += 1
        for v in cur.verts:
            for nf in v.link_faces:
                if nf not in visited and nf.material_index == leaf_mat_idx:
                    visited.add(nf)
                    comp.append(nf)
    if isl_idx % 12 != 0:
        to_del.extend(comp)
    else:
        iverts = list({v for cf in comp for v in cf.verts})
        c = sum((v.co for v in iverts), Vector((0.0, 0.0, 0.0))) / len(iverts)
        for v in iverts:
            v.co = c + (v.co - c) * 1.65
    isl_idx += 1

if to_del:
    bmesh.ops.delete(bm, geom=to_del, context="FACES")
bm.to_mesh(tree_obj.data)
bm.free()

# Map material names cleanly to M_Foliage_Tree_Branch, M_Foliage_Tree_Leaves, M_Foliage_Tree_Trunk
new_tree_mats = []
for m in tree_obj.data.materials:
    mname = m.name if m else ""
    if "leaves" in mname:
        new_tree_mats.append(get_or_make_mat("M_Foliage_Tree_Leaves", (0.28, 0.44, 0.18)))
    elif "branch" in mname:
        new_tree_mats.append(get_or_make_mat("M_Foliage_Tree_Branch", (0.36, 0.31, 0.26)))
    else:
        new_tree_mats.append(get_or_make_mat("M_Foliage_Tree_Trunk", (0.32, 0.28, 0.23)))
for idx, nm in enumerate(new_tree_mats):
    tree_obj.data.materials[idx] = nm
from collections import Counter
print("Prepared SM_Tree_Small_02 islands=", isl_idx, "polys=", len(tree_obj.data.polygons), "mat_counts=", Counter(p.material_index for p in tree_obj.data.polygons))


# ---------------------------------------------------------------------------
# 7. Build Garden Hardscape Centered at House Origin (Terrace + Gravel Strip)
# ---------------------------------------------------------------------------
def build_multi_box_mesh(obj_name, boxes, mat_name, color_rgb, uv_scale=0.45):
    bm_b = bmesh.new()
    for (x0, y0, x1, y1, z0, z1) in boxes:
        v0 = bm_b.verts.new((x0, y0, z0))
        v1 = bm_b.verts.new((x1, y0, z0))
        v2 = bm_b.verts.new((x1, y1, z0))
        v3 = bm_b.verts.new((x0, y1, z0))
        v4 = bm_b.verts.new((x0, y0, z1))
        v5 = bm_b.verts.new((x1, y0, z1))
        v6 = bm_b.verts.new((x1, y1, z1))
        v7 = bm_b.verts.new((x0, y1, z1))
        for fverts in [(v3, v2, v1, v0), (v4, v5, v6, v7), (v0, v1, v5, v4), (v1, v2, v6, v5), (v2, v3, v7, v6), (v3, v0, v4, v7)]:
            bm_b.faces.new(fverts)
    bm_b.normal_update()
    uv_lay = bm_b.loops.layers.uv.verify()
    for f in bm_b.faces:
        f.smooth = False
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for lp in f.loops:
            co = lp.vert.co
            if az >= ax and az >= ay:
                lp[uv_lay].uv = (co.x * uv_scale, co.y * uv_scale)
            elif ax >= ay:
                lp[uv_lay].uv = (co.y * uv_scale, co.z * uv_scale)
            else:
                lp[uv_lay].uv = (co.x * uv_scale, co.z * uv_scale)
    me_b = bpy.data.meshes.new(obj_name)
    bm_b.to_mesh(me_b)
    bm_b.free()
    ob_b = bpy.data.objects.new(obj_name, me_b)
    main_col.objects.link(ob_b)
    me_b.materials.append(get_or_make_mat(mat_name, color_rgb))
    return ob_b


# L-shaped Garden Terrace on North (y=8.40..10.95) and East (x=10.30..11.35) + lower step
terrace_boxes = [
    (2.40, 8.40, 11.35, 10.95, -0.25, -0.02),
    (10.30, 3.35, 11.35, 8.40, -0.25, -0.02),
    # Lower perimeter step around the terrace
    (2.10, 10.95, 11.65, 11.30, -0.25, -0.13),
    (11.35, 3.05, 11.65, 10.95, -0.25, -0.13),
    (2.10, 8.40, 2.40, 10.95, -0.25, -0.13),
]
build_multi_box_mesh("SM_Garden_Terrace", terrace_boxes, "M_Terrace_Paver_Grey", (0.58, 0.59, 0.60), uv_scale=0.45)

# Gravel Drainage Strip (50cm wide) around remaining foundation plinth walls
gravel_boxes = [
    (2.48, -0.52, 10.82, 0.00, -0.25, -0.215),
    (10.30, 0.00, 10.82, 3.05, -0.25, -0.215),
    (-0.52, 0.00, 0.00, 8.92, -0.25, -0.215),
    (0.00, 8.40, 2.10, 8.92, -0.25, -0.215),
]
build_multi_box_mesh("SM_Gravel_Drainage_Strip", gravel_boxes, "M_Gravel_Pebbles", (0.52, 0.50, 0.47), uv_scale=0.85)

# Dark Granite Curb edging the gravel strip
curb_boxes = [
    (2.48, -0.58, 10.88, -0.52, -0.25, -0.205),
    (10.82, -0.52, 10.88, 3.05, -0.25, -0.205),
    (-0.58, -0.06, -0.52, 8.98, -0.25, -0.205),
    (-0.52, 8.92, 2.10, 8.98, -0.25, -0.205),
]
build_multi_box_mesh("SM_Gravel_Curb", curb_boxes, "M_Window_Frame_Anthracite", (0.12, 0.13, 0.15), uv_scale=0.5)


# ---------------------------------------------------------------------------
# 8. Build Undulating 3D Terrain (SM_Terrain_Undulating_Lawn) & Dense 3D Grass Carpet (SM_Lawn_Turf_Carpet_3D)
# ---------------------------------------------------------------------------
hardscape_rects = [
    (-0.60, -0.60, 10.90, 9.00),   # House + Gravel Strip + Curb
    (-0.05, -0.65, 2.52, 0.05),    # Entrance Steps
    (0.40, -7.55, 2.30, 0.00),     # Entrance Walkway
    (2.06, 8.38, 11.68, 11.33),    # North Garden Terrace + Step
    (10.28, 3.02, 11.68, 8.45),    # East Garden Terrace + Step
]


def dist_to_hardscape(x, y):
    dmin = 999.0
    for (rx0, ry0, rx1, ry1) in hardscape_rects:
        dx = max(rx0 - x, 0.0, x - rx1)
        dy = max(ry0 - y, 0.0, y - ry1)
        d = math.hypot(dx, dy)
        if d < dmin:
            dmin = d
    return dmin


def terrain_z(x, y):
    z_base = -0.242
    d = dist_to_hardscape(x, y)
    if d <= 0.08:
        return z_base
    t = min(1.0, (d - 0.08) / 1.65)
    blend = t * t * (3.0 - 2.0 * t)
    # Multi-scale natural lawn undulations (visible gentle rolling swells & dips of -12cm to +32cm)
    w1 = 0.115 * math.sin(0.55 * x + 0.42 * y + 0.4) * math.cos(0.48 * y - 0.28 * x)
    w2 = 0.075 * math.sin(1.18 * x - 0.88 * y + 1.2)
    w3 = 0.045 * math.cos(1.90 * x + 1.70 * y - 0.7)
    # Gentle natural garden mounds in front yard (x=8.2, y=-3.2), East lawn (x=13.4, y=5.2), and North garden (x=6.8, y=14.0)
    m1 = 0.16 * math.exp(-((x - 8.2) ** 2 + (y + 3.1) ** 2) / 9.0)
    m2 = 0.18 * math.exp(-((x - 13.4) ** 2 + (y - 5.2) ** 2) / 10.0)
    m3 = 0.19 * math.exp(-((x - 6.8) ** 2 + (y - 14.0) ** 2) / 11.5)
    m4 = 0.14 * math.exp(-((x + 2.2) ** 2 + (y + 3.5) ** 2) / 8.0)
    return z_base + blend * (w1 + w2 + w3 + m1 + m2 + m3 + m4)


bm_terr = bmesh.new()
# Non-uniform grid: high density in [-18..+28m] around the house, extending out to [-92..+98m] past the 85m SkyDome
xs_terr = [-92.0 + 74.0 * (i / 10) for i in range(10)] + [-18.0 + 46.0 * (i / 140) for i in range(141)] + [28.0 + 70.0 * (i / 10) for i in range(1, 11)]
ys_terr = [-92.0 + 74.0 * (j / 10) for j in range(10)] + [-18.0 + 46.0 * (j / 140) for j in range(141)] + [28.0 + 70.0 * (j / 10) for j in range(1, 11)]

t_grid = []
for y in ys_terr:
    row = []
    for x in xs_terr:
        row.append(bm_terr.verts.new((x, y, terrain_z(x, y))))
    t_grid.append(row)

uv_terr = bm_terr.loops.layers.uv.verify()
for iy in range(len(ys_terr) - 1):
    for ix in range(len(xs_terr) - 1):
        v00 = t_grid[iy][ix]
        v10 = t_grid[iy][ix + 1]
        v11 = t_grid[iy + 1][ix + 1]
        v01 = t_grid[iy + 1][ix]
        fc = bm_terr.faces.new((v00, v10, v11, v01))
        fc.smooth = True
        for lp in fc.loops:
            co = lp.vert.co
            lp[uv_terr].uv = (co.x * 0.45, co.y * 0.45)

bm_terr.normal_update()
me_terr = bpy.data.meshes.new("SM_Terrain_Undulating_Lawn")
bm_terr.to_mesh(me_terr)
bm_terr.free()
obj_terr = bpy.data.objects.new("SM_Terrain_Undulating_Lawn", me_terr)
main_col.objects.link(obj_terr)
me_terr.materials.append(get_or_make_mat("M_ParcelGrass", (0.26, 0.46, 0.18)))
print("Prepared SM_Terrain_Undulating_Lawn polys=", len(me_terr.polygons))

# Build Dense 3D Curved Grass Blade Carpet (SM_Lawn_Turf_Carpet_3D) — 100% true 3D tapered blades, ZERO rectangular cards
bm_carpet = bmesh.new()
uv_carpet = bm_carpet.loops.layers.uv.verify()
rng_c = random.Random(202611)

step_g = 0.24
gx_vals = [(-4.8 + i * step_g) for i in range(int((16.0 - (-4.8)) / step_g))]
gy_vals = [(-7.2 + j * step_g) for j in range(int((17.2 - (-7.2)) / step_g))]

clump_count = 0
for gx_base in gx_vals:
    for gy_base in gy_vals:
        cx = gx_base + rng_c.uniform(-0.10, 0.10)
        cy = gy_base + rng_c.uniform(-0.10, 0.10)
        d_hs = dist_to_hardscape(cx, cy)
        if d_hs < 0.02:
            continue
        if d_hs > 8.0 and rng_c.random() < 0.45:
            continue
        cz = terrain_z(cx, cy) - 0.006
        h_scale = min(1.0, 0.55 + d_hs * 0.50)
        # 9 true 3D curved, tapered grass blades per tuft fanning out organically
        n_blades = 9
        base_rot = rng_c.uniform(0.0, math.tau)
        for b_i in range(n_blades):
            ang = base_rot + b_i * (math.tau / n_blades) + rng_c.uniform(-0.25, 0.25)
            ca, sa = math.cos(ang), math.sin(ang)
            # Radial offset from tuft center
            r0 = rng_c.uniform(0.01, 0.09)
            bx = cx + ca * r0
            by = cy + sa * r0
            # Blade width perpendicular to radial direction
            w0 = rng_c.uniform(0.009, 0.015)
            px, py = -sa * w0, ca * w0
            h_b = rng_c.uniform(0.055, 0.135) * h_scale
            arch = rng_c.uniform(0.035, 0.095) * h_scale
            # Midpoint & tip of curved 3D blade
            mx = bx + ca * (arch * 0.45)
            my = by + sa * (arch * 0.45)
            mz = cz + h_b * 0.55
            tx = bx + ca * arch
            ty = by + sa * arch
            tz = cz + h_b
            vb0 = bm_carpet.verts.new((bx - px, by - py, cz))
            vb1 = bm_carpet.verts.new((bx + px, by + py, cz))
            vm0 = bm_carpet.verts.new((mx - px * 0.55, my - py * 0.55, mz))
            vm1 = bm_carpet.verts.new((mx + px * 0.55, my + py * 0.55, mz))
            vtip = bm_carpet.verts.new((tx, ty, tz))
            f1 = bm_carpet.faces.new((vb0, vb1, vm1, vm0))
            f2 = bm_carpet.faces.new((vm0, vm1, vtip))
            f1.smooth = True
            f2.smooth = True
            for lp in f1.loops:
                lp[uv_carpet].uv = (lp.vert.co.x * 0.45, lp.vert.co.y * 0.45)
            for lp in f2.loops:
                lp[uv_carpet].uv = (lp.vert.co.x * 0.45, lp.vert.co.y * 0.45)
        clump_count += 1

bm_carpet.normal_update()
me_carpet = bpy.data.meshes.new("SM_Lawn_Turf_Carpet_3D")
bm_carpet.to_mesh(me_carpet)
bm_carpet.free()
obj_carpet = bpy.data.objects.new("SM_Lawn_Turf_Carpet_3D", me_carpet)
main_col.objects.link(obj_carpet)
me_carpet.materials.append(get_or_make_mat("M_ParcelGrass", (0.28, 0.48, 0.18)))
print("Prepared SM_Lawn_Turf_Carpet_3D clumps=", clump_count, "polys=", len(me_carpet.polygons))


# ---------------------------------------------------------------------------
# 8. Build 360-degree Panoramic Environment SkyDome (Radius = 85m, centered at house)
# ---------------------------------------------------------------------------
bm_sky = bmesh.new()
cx_sky, cy_sky = 5.15, 4.20
R_sky = 85.0
n_lon = 72
n_lat = 32
# Latitudes from -8 deg (below horizon so no gap at ground) to +75 deg
lat_angles = [math.radians(-8.0 + (83.0 * i / n_lat)) for i in range(n_lat + 1)]
lon_angles = [math.tau * j / n_lon for j in range(n_lon + 1)]

verts_grid = []
for i, lat in enumerate(lat_angles):
    row = []
    clat = math.cos(lat)
    slat = math.sin(lat)
    for j, lon in enumerate(lon_angles):
        # Clamp z slightly below ground for bottom ring so horizon sits naturally at eye level
        x = cx_sky + R_sky * clat * math.cos(lon)
        y = cy_sky + R_sky * clat * math.sin(lon)
        z = R_sky * slat
        if z < -1.5:
            z = -1.5
        row.append(bm_sky.verts.new((x, y, z)))
    verts_grid.append(row)

uv_sky = bm_sky.loops.layers.uv.verify()
for i in range(n_lat):
    # Map latitude so horizon (lat=0) corresponds to V=0.50 of the equirectangular panorama
    # In Blender/OpenGL UV space, V=0.50 is exact horizon of equirectangular JPG!
    v0_uv = 0.50 + (lat_angles[i] / (0.5 * math.pi)) * 0.48
    v1_uv = 0.50 + (lat_angles[i + 1] / (0.5 * math.pi)) * 0.48
    for j in range(n_lon):
        u0_uv = j / n_lon
        u1_uv = (j + 1) / n_lon
        va = verts_grid[i][j]
        vb = verts_grid[i][j + 1]
        vc = verts_grid[i + 1][j + 1]
        vd = verts_grid[i + 1][j]
        # Inward-facing normal (clockwise from outside = counter-clockwise from inside)
        face = bm_sky.faces.new((va, vd, vc, vb))
        face.smooth = True
        face.loops[0][uv_sky].uv = (u0_uv, v0_uv)
        face.loops[1][uv_sky].uv = (u0_uv, v1_uv)
        face.loops[2][uv_sky].uv = (u1_uv, v1_uv)
        face.loops[3][uv_sky].uv = (u1_uv, v0_uv)

bm_sky.normal_update()
me_sky = bpy.data.meshes.new("SM_Env_SkyDome")
bm_sky.to_mesh(me_sky)
bm_sky.free()
obj_sky = bpy.data.objects.new("SM_Env_SkyDome", me_sky)
main_col.objects.link(obj_sky)
me_sky.materials.append(get_or_make_mat("M_Env_Panorama_Sky", (0.65, 0.78, 0.92)))
print("Prepared SM_Env_SkyDome polys=", len(me_sky.polygons))

for o in bpy.data.objects:
    if o.type == "MESH" and o.data.uv_layers:
        uvd = o.data.uv_layers.active.data
        us = [d.uv[0] for d in uvd] if uvd else [0.0]
        vs = [d.uv[1] for d in uvd] if uvd else [0.0]
        print(f"UV_CHECK {o.name:26s} uv_layers={[l.name for l in o.data.uv_layers]} U=[{min(us):.2f}..{max(us):.2f}] V=[{min(vs):.2f}..{max(vs):.2f}]")

# Export all to foliage_and_env.fbx
bpy.ops.export_scene.fbx(
    filepath=out_fbx,
    use_selection=False,
    apply_scale_options="FBX_SCALE_ALL",
    axis_forward="-Z",
    axis_up="Y",
    mesh_smooth_type="FACE",
    path_mode="AUTO",
)
print("EXPORTED_FOLIAGE_FBX_OK", out_fbx, "size_mb=", round(os.path.getsize(out_fbx) / (1024 * 1024), 2))

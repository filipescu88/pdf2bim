"""Blender 5.1 headless Cycles archviz render: FBX house + procedural Nishita sky + ground. Run via --python-exit-code 1.

Usage: blender -b --python-exit-code 1 --python blender_render_cycles.py -- <in.fbx> <out.png> [samples] [width] [height] [device]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
in_fbx, out_png = argv[0], argv[1]
samples = int(argv[2]) if len(argv) > 2 else 128
W = int(argv[3]) if len(argv) > 3 else 1920
H = int(argv[4]) if len(argv) > 4 else 1080
device = argv[5] if len(argv) > 5 else "AUTO"
tex_dir = os.environ.get("PDF2BIM_TEX_DIR", "C:/Users/filip/pdf2bim_remote/textures")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=in_fbx)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

# ---- bounds (house only, ignore big env boxes) ----
house = [o for o in meshes if "Garden_Lawn" not in o.name and "SkyDome" not in o.name]
pts = [o.matrix_world @ Vector(c) for o in house for c in o.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
print("BOUNDS", tuple(mn), tuple(mx))
ctr = (mn + mx) / 2

# remove lawn boxes: replaced by large ground below
for o in meshes:
    if "Garden_Lawn" in o.name:
        bpy.data.objects.remove(o)

# ---- material tuning for Cycles ----
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf:
        continue
    print("MAT", mat.name, tuple(round(v,2) for v in bsdf.inputs["Base Color"].default_value), [n.image.name for n in mat.node_tree.nodes if n.type=="TEX_IMAGE" and n.image])
    if mat.name.startswith("M_Glass"):
        bsdf.inputs["Base Color"].default_value = (0.85, 0.95, 0.95, 1)
        bsdf.inputs["Roughness"].default_value = 0.0
        bsdf.inputs["IOR"].default_value = 1.5
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["Alpha"].default_value = 1.0
        mat.blend_method = "OPAQUE" if hasattr(mat, "blend_method") else None
    elif mat.name.startswith("M_Window_Frame"):
        bsdf.inputs["Roughness"].default_value = 0.5
        bsdf.inputs["Metallic"].default_value = 0.05
    elif mat.name.startswith("M_Roof"):
        bsdf.inputs["Roughness"].default_value = 0.7


# ---- mineral stucco: keep the scanned plaster PBR, add warm tone, weathering, stronger grain ----
def enhance_stucco(mat):
    nt_ = mat.node_tree
    bs = nt_.nodes.get("Principled BSDF")
    if not bs or not bs.inputs["Base Color"].links:
        return
    geo = nt_.nodes.new("ShaderNodeNewGeometry")
    def noise(scale, detail, rough=0.55):
        n_ = nt_.nodes.new("ShaderNodeTexNoise")
        n_.inputs["Scale"].default_value = scale
        n_.inputs["Detail"].default_value = detail
        n_.inputs["Roughness"].default_value = rough
        nt_.links.new(geo.outputs["Position"], n_.inputs["Vector"])
        return n_
    low = noise(1.1, 3)
    mid = noise(5.0, 4)
    grain = noise(160.0, 6, 0.7)
    src = bs.inputs["Base Color"].links[0].from_socket
    # warm, slightly uneven tone
    ramp = nt_.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[0].color = (0.80, 0.74, 0.62, 1)
    ramp.color_ramp.elements[1].color = (1.0, 0.95, 0.85, 1)
    nt_.links.new(low.outputs["Fac"], ramp.inputs["Fac"])
    tone = nt_.nodes.new("ShaderNodeMix")
    tone.data_type = "RGBA"
    tone.blend_type = "MULTIPLY"
    tone.inputs[0].default_value = 1.0
    nt_.links.new(src, tone.inputs[6])
    nt_.links.new(ramp.outputs["Color"], tone.inputs[7])
    # splash/dirt zone near ground + soft streaks from the eave
    sep = nt_.nodes.new("ShaderNodeSeparateXYZ")
    nt_.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    mr = nt_.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 1.0
    mr.inputs["To Min"].default_value = 1.0
    mr.inputs["To Max"].default_value = 0.0
    nt_.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mulm = nt_.nodes.new("ShaderNodeMath")
    mulm.operation = "MULTIPLY"
    mulm.inputs[1].default_value = 1.4
    nt_.links.new(mr.outputs["Result"], mulm.inputs[0])
    patch = nt_.nodes.new("ShaderNodeMath")
    patch.operation = "MULTIPLY"
    nt_.links.new(mulm.outputs["Value"], patch.inputs[0])
    nt_.links.new(mid.outputs["Fac"], patch.inputs[1])
    clampm = nt_.nodes.new("ShaderNodeMath")
    clampm.operation = "MULTIPLY"
    clampm.use_clamp = True
    clampm.inputs[1].default_value = 1.2
    nt_.links.new(patch.outputs["Value"], clampm.inputs[0])
    dirt = nt_.nodes.new("ShaderNodeMix")
    dirt.data_type = "RGBA"
    dirt.inputs[7].default_value = (0.22, 0.20, 0.15, 1)
    nt_.links.new(clampm.outputs["Value"], dirt.inputs[0])
    nt_.links.new(tone.outputs[2], dirt.inputs[6])
    nt_.links.new(dirt.outputs[2], bs.inputs["Base Color"])
    # stronger grain on top of the scanned normal map
    for n_ in nt_.nodes:
        if n_.type == "NORMAL_MAP":
            n_.inputs["Strength"].default_value = 2.2
            bump = nt_.nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value = 0.5
            bump.inputs["Distance"].default_value = 0.01
            nt_.links.new(grain.outputs["Fac"], bump.inputs["Height"])
            nt_.links.new(n_.outputs["Normal"], bump.inputs["Normal"])
            nt_.links.new(bump.outputs["Normal"], bs.inputs["Normal"])

for _m_ in bpy.data.materials:
    if _m_.name.startswith("M_Wall_Plaster") and _m_.use_nodes:
        enhance_stucco(_m_)

# ---- bevel on all non-glass meshes for soft edge highlights ----
for o in house:
    if o.type == "MESH" and o.data.polygons and not any(s.material and s.material.name.startswith("M_Glass") for s in o.material_slots):
        if len(o.data.polygons) < 20000:
            m = o.modifiers.new("bev", "BEVEL")
            m.width = 0.006
            m.segments = 2
            m.limit_method = "ANGLE"

# ---- ground ----
bpy.ops.mesh.primitive_grid_add(x_subdivisions=300, y_subdivisions=300, size=300, location=(ctr.x, ctr.y, -0.24))
ground = bpy.context.active_object
import math as _m
vg = ground.vertex_groups.new(name="far")
for v in ground.data.vertices:
    dx, dy = v.co.x - 5.0, v.co.y - 4.0
    t = max(0.0, min(1.0, (_m.hypot(dx, dy) - 16.0) / 30.0))
    vg.add([v.index], t * t * (3 - 2 * t), "REPLACE")
ctex = bpy.data.textures.new("terrain", "CLOUDS")
ctex.noise_scale = 28.0
ctex.noise_depth = 2
dm = ground.modifiers.new("hills", "DISPLACE")
dm.texture = ctex
dm.vertex_group = "far"
dm.strength = 5.0
dm.mid_level = 0.45
dm.texture_coords = "GLOBAL"
bpy.ops.object.shade_smooth()
ground.name = "Ground"
gm = bpy.data.materials.new("M_Ground")
gm.use_nodes = True
nt = gm.node_tree
b = nt.nodes["Principled BSDF"]
b.inputs["Roughness"].default_value = 0.95
tc = nt.nodes.new("ShaderNodeTexCoord")
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)
nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
noise = nt.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 0.35
noise.inputs["Detail"].default_value = 8
nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color = (0.08, 0.16, 0.035, 1)
ramp.color_ramp.elements[1].color = (0.20, 0.27, 0.07, 1)
nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
turf = nt.nodes.new("ShaderNodeTexImage")
turf_p = tex_dir + "/lawn_turf_2k_diffuse.jpg"
if os.path.isfile(turf_p):
    turf.image = bpy.data.images.load(turf_p)
    mp2 = nt.nodes.new("ShaderNodeMapping")
    mp2.inputs["Scale"].default_value = (0.25, 0.25, 0.25)
    nt.links.new(tc.outputs["Object"], mp2.inputs["Vector"])
    nt.links.new(mp2.outputs["Vector"], turf.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    nt.links.new(turf.outputs["Color"], mix.inputs[7])
    ramp.color_ramp.elements[0].color = (0.55, 0.7, 0.35, 1)
    ramp.color_ramp.elements[1].color = (1.1, 1.1, 0.6, 1)
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
else:
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
disp_noise = nt.nodes.new("ShaderNodeTexNoise")
disp_noise.inputs["Scale"].default_value = 90
nt.links.new(tc.outputs["Object"], disp_noise.inputs["Vector"])
bump = nt.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.6
bump.inputs["Distance"].default_value = 0.05
nt.links.new(disp_noise.outputs["Fac"], bump.inputs["Height"])
nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
ground.data.materials.append(gm)


# ---- foliage (photoscanned Poly Haven trees/shrubs) ----
import random
fol_dir = os.environ.get("PDF2BIM_FOL_DIR", "C:/Users/filip/pdf2bim_remote/foliage")
FOL_MATS = {
    "tree_small_02_branches": ("tree_small_02_branch_diff_1k.jpg", "tree_small_02_branch_alpha_1k.jpg"),
    "tree_small_02_leaves": ("tree_small_02_leaves_diff_1k.jpg", "tree_small_02_leaves_alpha_1k.jpg"),
    "tree_small_02_trunk": ("tree_small_02_diff_1k.jpg", None),
    "shrub_02": ("shrub_02_diff_1k.jpg", "shrub_02_alpha_1k.jpg"),
}

def fol_material(name):
    base = next((k for k in FOL_MATS if name.startswith(k)), None)
    m = bpy.data.materials.new("F_" + name)
    m.use_nodes = True
    nt2 = m.node_tree
    bs = nt2.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.65
    if base:
        d, a = FOL_MATS[base]
        if os.path.isfile(f"{tex_dir}/{d}"):
            t = nt2.nodes.new("ShaderNodeTexImage")
            t.image = bpy.data.images.load(f"{tex_dir}/{d}")
            nt2.links.new(t.outputs["Color"], bs.inputs["Base Color"])
        if a and os.path.isfile(f"{tex_dir}/{a}"):
            t = nt2.nodes.new("ShaderNodeTexImage")
            t.image = bpy.data.images.load(f"{tex_dir}/{a}")
            t.image.colorspace_settings.name = "Non-Color"
            nt2.links.new(t.outputs["Color"], bs.inputs["Alpha"])
    return m

def import_fol(fname):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(fol_dir, fname))
    new = [o for o in set(bpy.data.objects) - before]
    meshes_ = [o for o in new if o.type == "MESH"]
    for o in meshes_:
        o.parent = None
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes_:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes_[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in meshes_:
        for i, sl in enumerate(o.material_slots):
            o.material_slots[i].material = fol_material(sl.material.name if sl.material else o.name)
        o.hide_render = True  # templates; instances placed below
        zmin = min(v.co.z for v in o.data.vertices)
        for v in o.data.vertices:
            v.co.z -= zmin
    return meshes_

_dg = bpy.context.evaluated_depsgraph_get()
_ground_eval = ground.evaluated_get(_dg)

def ground_z(x, y):
    """Exact terrain height (world Z) at x,y via ray cast onto the displaced ground."""
    org = Vector((x - ground.location.x, y - ground.location.y, 50.0))
    ok, hit, _n, _i = _ground_eval.ray_cast(org, Vector((0, 0, -1)), distance=200.0)
    return hit.z + ground.location.z if ok else ground.location.z

def place(tpl, loc, rot, scl):
    o = tpl.copy()
    o.hide_render = False
    o.location = (loc[0], loc[1], ground_z(loc[0], loc[1]) - 0.06)
    o.rotation_euler = (0, 0, rot)
    o.scale = (scl, scl, scl)
    bpy.context.scene.collection.objects.link(o)
    return o

rnd = random.Random(7)
gz = -0.24
try:
    tree_t = import_fol("tree_small_02_1k.fbx")
    for (x, y, sc_) in [(-6.5, 3.0, 1.9), (15.5, 7.0, 2.2), (23.0, -6.0, 1.8), (-3.0, 16.0, 2.4), (9.0, 22.0, 2.6), (19.0, 1.0, 1.6), (-10.0, -5.0, 1.5), (30.0, 12.0, 2.4), (4.0, 28.0, 2.8), (14.0, 31.0, 3.0), (-8.0, 26.0, 2.6), (24.0, 22.0, 2.8), (-16.0, 12.0, 2.5)]:
        for t in tree_t:
            place(t, (x, y, gz), rnd.uniform(0, 6.28), sc_)
    _size = max(mx.x - mn.x, mx.y - mn.y)
    _cx, _cy = ctr.x - _size * 0.55, mn.y - _size * 0.65 + 6.0
    _base = _m.atan2(ctr.y - _cy, ctr.x - _cx)
    for i in range(22):
        ang = _base + _m.radians(rnd.uniform(-48, 48))
        rad = rnd.uniform(45, 85)
        place(tree_t[0], (_cx + rad * _m.cos(ang), _cy + rad * _m.sin(ang), gz + 1.8), rnd.uniform(0, 6.28), rnd.uniform(3.0, 4.4))
except Exception as e:
    print("TREE_FAIL", e)

# ---- boxwood shrubs (procedural displaced spheres with boxwood PBR) ----
def boxwood_material():
    m = bpy.data.materials.new("M_Boxwood")
    m.use_nodes = True
    n = m.node_tree
    bs = n.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.6
    coord = n.nodes.new("ShaderNodeTexCoord")
    mapn = n.nodes.new("ShaderNodeMapping")
    mapn.inputs["Scale"].default_value = (2.2, 2.2, 2.2)
    n.links.new(coord.outputs["Object"], mapn.inputs["Vector"])
    def tex(fn, nc=False):
        t = n.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(f"{tex_dir}/{fn}")
        t.projection = "BOX"
        t.projection_blend = 0.3
        if nc:
            t.image.colorspace_settings.name = "Non-Color"
        n.links.new(mapn.outputs["Vector"], t.inputs["Vector"])
        return t
    if os.path.isfile(f"{tex_dir}/hedge_boxwood_diffuse.jpg"):
        d = tex("hedge_boxwood_diffuse.jpg")
        hs2 = n.nodes.new("ShaderNodeHueSaturation")
        hs2.inputs["Value"].default_value = 0.8
        n.links.new(d.outputs["Color"], hs2.inputs["Color"])
        n.links.new(hs2.outputs["Color"], bs.inputs["Base Color"])
        nm = tex("hedge_boxwood_nor_gl.jpg", True)
        nmap = n.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 1.5
        n.links.new(nm.outputs["Color"], nmap.inputs["Color"])
        n.links.new(nmap.outputs["Normal"], bs.inputs["Normal"])
    else:
        bs.inputs["Base Color"].default_value = (0.08, 0.2, 0.05, 1)
    return m

box_mat = boxwood_material()
cl = bpy.data.textures.new("bushclouds", "CLOUDS")
cl.noise_scale = 0.35
cl.noise_depth = 3
def leaf_material():
    m = bpy.data.materials.new("M_BushLeaf")
    m.use_nodes = True
    n = m.node_tree
    bs = n.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.55
    d, a = "tree_small_02_leaves_diff_1k.jpg", "tree_small_02_leaves_alpha_1k.jpg"
    if os.path.isfile(f"{tex_dir}/{d}"):
        t = n.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(f"{tex_dir}/{d}")
        hs3 = n.nodes.new("ShaderNodeHueSaturation")
        hs3.inputs["Value"].default_value = 0.5
        hs3.inputs["Saturation"].default_value = 1.1
        hs3.inputs["Hue"].default_value = 0.56
        n.links.new(t.outputs["Color"], hs3.inputs["Color"])
        n.links.new(hs3.outputs["Color"], bs.inputs["Base Color"])
        ta = n.nodes.new("ShaderNodeTexImage")
        ta.image = bpy.data.images.load(f"{tex_dir}/{a}")
        ta.image.colorspace_settings.name = "Non-Color"
        n.links.new(ta.outputs["Color"], bs.inputs["Alpha"])
    return m

leaf_mat = leaf_material()

def add_leaf_cards(x, y, r, zc, sx, sy, sz_, count):
    import bmesh as _bm
    me = bpy.data.meshes.new("bush_leaves")
    bm = _bm.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for _ in range(count):
        u, v = rnd.uniform(0, 6.283), rnd.uniform(-0.15, 1.0)
        rr = r * rnd.uniform(0.9, 1.12)
        cphi = _m.sqrt(max(0.0, 1 - v * v))
        n = Vector((cphi * _m.cos(u) / sx, cphi * _m.sin(u) / sy, v / sz_)).normalized()
        pos = Vector((x + rr * sx * cphi * _m.cos(u), y + rr * sy * cphi * _m.sin(u), zc + rr * sz_ * v))
        t1 = n.cross(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))).normalized()
        t2 = n.cross(t1).normalized()
        sz = rnd.uniform(0.22, 0.38)
        pts = [pos + (-t1 - t2) * sz * 0.5, pos + (t1 - t2) * sz * 0.5, pos + (t1 + t2) * sz * 0.5, pos + (-t1 + t2) * sz * 0.5]
        f = bm.faces.new([bm.verts.new(p_) for p_ in pts])
        for lp, uv in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            lp[uvl].uv = uv
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("bush_leaves", me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(leaf_mat)
    return ob

def add_bush(x, y, r, sz=1.0, seed=0):
    gzl = ground_z(x, y)
    sy_ = rnd.uniform(0.85, 1.1)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=r * 0.88, location=(x, y, gzl + r * 0.55 * sz))
    o = bpy.context.active_object
    o.scale = (1.0, sy_, 0.7 * sz)
    add_leaf_cards(x, y, r, gzl + r * 0.55 * sz, 1.0, sy_, 0.7 * sz, int(1100 * r * r / 0.25))
    bpy.ops.object.shade_smooth()
    d = o.modifiers.new("disp", "DISPLACE")
    d.texture = cl
    d.strength = r * 0.35
    d.mid_level = 0.45
    d.texture_coords = "OBJECT"
    o.data.materials.append(box_mat)
    return o

for (x, y, r) in [(-1.0, -0.25, 0.55), (-1.1, 1.2, 0.5), (3.5, -0.75, 0.55), (4.5, -0.8, 0.45), (6.9, -0.75, 0.6), (8.3, -0.75, 0.5), (9.4, -0.8, 0.42), (11.2, 0.8, 0.55), (11.3, 2.6, 0.5), (2.9, -1.4, 0.4), (0.0, -1.6, 0.45)]:
    add_bush(x, y, r)

# ---- sky + sun ----
world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
sky = wn.new("ShaderNodeTexSky")
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_elevation = math.radians(float(os.environ.get("SUN_EL","24")))
sky.sun_rotation = math.radians(float(os.environ.get("SUN_ROT","150")))
sky.sun_size = math.radians(0.6)
sky.air_density = 1.0
bg = wn["Background"]
bg.inputs["Strength"].default_value = 1.0
hdri_path = os.environ.get("PDF2BIM_HDRI", "C:/Users/filip/pdf2bim_remote/textures/sky_clouds_4k.hdr")
if os.path.isfile(hdri_path):
    # Nishita lights the scene; HDRI (clouds) is only what the camera sees.
    wl = world.node_tree.links
    env = wn.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri_path)
    wc = wn.new("ShaderNodeTexCoord")
    wm = wn.new("ShaderNodeMapping")
    wm.inputs["Rotation"].default_value[2] = math.radians(float(os.environ.get("HDRI_ROT", "0")))
    wl.new(wc.outputs["Generated"], wm.inputs["Vector"])
    wl.new(wm.inputs["Vector"].links[0].from_socket if False else wm.outputs["Vector"], env.inputs["Vector"])
    lp = wn.new("ShaderNodeLightPath")
    mixs = wn.new("ShaderNodeMixShader")
    bg2 = wn.new("ShaderNodeBackground")
    bg2.inputs["Strength"].default_value = float(os.environ.get("HDRI_STR", "0.9"))
    hs = wn.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = float(os.environ.get("SKY_SAT", "0.72"))
    hs.inputs["Value"].default_value = 1.0
    wl.new(env.outputs["Color"], hs.inputs["Color"])
    wl.new(hs.outputs["Color"], bg2.inputs["Color"])
    wl.new(sky.outputs["Color"], bg.inputs["Color"])
    wl.new(lp.outputs["Is Camera Ray"], mixs.inputs["Fac"])
    wl.new(bg.outputs["Background"], mixs.inputs[1])
    wl.new(bg2.outputs["Background"], mixs.inputs[2])
    out = wn["World Output"] if "World Output" in wn else wn.new("ShaderNodeOutputWorld")
    wl.new(mixs.outputs["Shader"], out.inputs["Surface"])
else:
    world.node_tree.links.new(sky.outputs["Color"], bg.inputs["Color"])

# ---- camera (architectural: 35mm, low eye height, vertical shift) ----
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 32
cam_data.sensor_width = 36
cam_data.dof.use_dof = False
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
size = max(mx.x - mn.x, mx.y - mn.y)
# house front (entrance) is toward -Y in this export; view from front-left corner
cam.location = (ctr.x - size * 0.55, mn.y - size * 0.65 + 6.0, mn.z + 1.6)
target = Vector((ctr.x - 0.0, ctr.y, mn.z + (mx.z - mn.z) * 0.35))
direction = target - cam.location
rot = direction.to_track_quat("-Z", "Y").to_euler()
rot.x = math.radians(90)  # keep verticals straight, use shift for framing
cam.rotation_euler = (rot.x, 0, rot.z)
cam_data.shift_y = 0.10

# ---- Cycles settings ----
sc = bpy.context.scene
sc.render.engine = "CYCLES"
cy = sc.cycles
cy.samples = samples
cy.use_denoising = True
cy.denoiser = "OPENIMAGEDENOISE"
cy.max_bounces = 8
cy.glossy_bounces = 6
cy.transmission_bounces = 8
cy.use_adaptive_sampling = True
cy.sample_clamp_indirect = 10.0
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_depth = "16"
sc.render.filepath = out_png
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - High Contrast"
sc.view_settings.exposure = float(os.environ.get("EXPO","-2.2"))

prefs = bpy.context.preferences.addons["cycles"].preferences
used = "CPU"
if device != "CPU":
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                used = kind
                break
        except Exception as e:
            print("device fail", kind, e)
sc.cycles.device = "GPU" if used != "CPU" else "CPU"
print("CYCLES_DEVICE", used, [(d.name, d.type, d.use) for d in prefs.devices])
if used != "CPU":
    sc.cycles.tile_size = 1024 if hasattr(sc.cycles, "tile_size") else None

bpy.ops.render.render(write_still=True)
print("RENDER_OK", out_png)

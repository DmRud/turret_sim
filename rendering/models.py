"""
Procedural 3D model generation for the turret simulator.
Creates all geometry programmatically (no external assets needed).
"""

import math
from panda3d.core import (
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomNode,
    LVector3, LVector4, LPoint3, LColor,
    NodePath, Material, TextureStage, Texture,
    CardMaker, LineSegs,
    TransparencyAttrib,
)


def make_cylinder(name, radius, height, segments=16, color=(0.5, 0.5, 0.5, 1)):
    """Create a cylinder mesh."""
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)

    vertex = GeomVertexWriter(vdata, 'vertex')
    normal = GeomVertexWriter(vdata, 'normal')
    col = GeomVertexWriter(vdata, 'color')

    tris = GeomTriangles(Geom.UHStatic)

    # Side vertices
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        nx = math.cos(angle)
        ny = math.sin(angle)

        # Bottom
        vertex.addData3(x, y, 0)
        normal.addData3(nx, ny, 0)
        col.addData4(*color)

        # Top
        vertex.addData3(x, y, height)
        normal.addData3(nx, ny, 0)
        col.addData4(*color)

    # Side faces
    for i in range(segments):
        base = i * 2
        tris.addVertices(base, base + 1, base + 2)
        tris.addVertices(base + 1, base + 3, base + 2)

    # Top cap
    cap_start = (segments + 1) * 2
    # Center top
    vertex.addData3(0, 0, height)
    normal.addData3(0, 0, 1)
    col.addData4(*color)
    center_top = cap_start

    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertex.addData3(x, y, height)
        normal.addData3(0, 0, 1)
        col.addData4(*color)

    for i in range(segments):
        tris.addVertices(center_top, center_top + 1 + i, center_top + 2 + i)

    # Bottom cap
    cap_bot = center_top + segments + 2
    vertex.addData3(0, 0, 0)
    normal.addData3(0, 0, -1)
    col.addData4(*color)
    center_bot = cap_bot

    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertex.addData3(x, y, 0)
        normal.addData3(0, 0, -1)
        col.addData4(*color)

    for i in range(segments):
        tris.addVertices(center_bot, center_bot + 2 + i, center_bot + 1 + i)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def make_box(name, sx, sy, sz, color=(0.5, 0.5, 0.5, 1)):
    """Create a box mesh centered at origin."""
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)

    vertex = GeomVertexWriter(vdata, 'vertex')
    normal = GeomVertexWriter(vdata, 'normal')
    col = GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)

    hx, hy, hz = sx/2, sy/2, sz/2

    faces = [
        # (normal, vertices)
        ((0, 0, 1), [(-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz)]),
        ((0, 0,-1), [(-hx,hy,-hz),(hx,hy,-hz),(hx,-hy,-hz),(-hx,-hy,-hz)]),
        ((0, 1, 0), [(-hx,hy,-hz),(-hx,hy,hz),(hx,hy,hz),(hx,hy,-hz)]),
        ((0,-1, 0), [(-hx,-hy,hz),(-hx,-hy,-hz),(hx,-hy,-hz),(hx,-hy,hz)]),
        ((1, 0, 0), [(hx,-hy,-hz),(hx,hy,-hz),(hx,hy,hz),(hx,-hy,hz)]),
        ((-1,0, 0), [(-hx,-hy,hz),(-hx,hy,hz),(-hx,hy,-hz),(-hx,-hy,-hz)]),
    ]

    idx = 0
    for n, verts in faces:
        for v in verts:
            vertex.addData3(*v)
            normal.addData3(*n)
            col.addData4(*color)
        tris.addVertices(idx, idx+1, idx+2)
        tris.addVertices(idx, idx+2, idx+3)
        idx += 4

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def make_sphere(name, radius, segments=12, rings=8, color=(0.5, 0.5, 0.5, 1)):
    """Create a UV sphere."""
    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData(name, fmt, Geom.UHStatic)

    vertex = GeomVertexWriter(vdata, 'vertex')
    normal = GeomVertexWriter(vdata, 'normal')
    col = GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)

    for j in range(rings + 1):
        phi = math.pi * j / rings
        for i in range(segments + 1):
            theta = 2 * math.pi * i / segments
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)
            nx, ny, nz = x/radius, y/radius, z/radius

            vertex.addData3(x, y, z)
            normal.addData3(nx, ny, nz)
            col.addData4(*color)

    for j in range(rings):
        for i in range(segments):
            p0 = j * (segments + 1) + i
            p1 = p0 + 1
            p2 = p0 + segments + 1
            p3 = p2 + 1
            tris.addVertices(p0, p2, p1)
            tris.addVertices(p1, p2, p3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def build_turret_model(parent: NodePath) -> dict:
    """
    Build a Browning M2 twin mount turret.
    Returns dict of sub-nodes for animation.
    
    Structure:
    - base_np: Fixed tripod base
    - yaw_np: Rotates on azimuth (child of base)
    - pitch_np: Rotates on elevation (child of yaw)
    - barrel_l_np, barrel_r_np: Gun barrels (children of pitch)
    - muzzle_l_np, muzzle_r_np: Muzzle flash points
    """
    # Colors
    metal_dark = (0.25, 0.25, 0.22, 1)
    metal_light = (0.4, 0.4, 0.35, 1)
    metal_barrel = (0.3, 0.3, 0.28, 1)

    # === TRIPOD BASE ===
    base_np = parent.attachNewNode("turret_base")

    # Tripod legs (3 legs) — each leg from foot on ground to hub on column.
    # The cylinder grows along local +Z. We place it at the foot, then
    # use a helper node with lookAt to orient +Z toward the hub.
    hub_z = 0.9       # Where legs converge on the column
    foot_radius = 0.6  # How far out the feet are from center
    for i in range(3):
        angle_rad = math.radians(i * 120)
        foot_x = foot_radius * math.sin(angle_rad)
        foot_y = foot_radius * math.cos(angle_rad)

        # Leg length
        leg_len = math.sqrt(foot_x**2 + foot_y**2 + hub_z**2)

        # Helper node at foot position — we orient this so its +Y points
        # toward the hub, then attach the cylinder rotated -90 pitch so
        # its +Z aligns with that direction.
        helper = base_np.attachNewNode(f"leg_helper_{i}")
        helper.setPos(foot_x, foot_y, 0)
        helper.lookAt(LPoint3(0, 0, hub_z))

        leg = make_cylinder(f"leg_{i}", 0.03, leg_len, 8, metal_dark)
        leg.reparentTo(helper)
        leg.setP(-90)  # Rotate so cylinder +Z aligns with helper +Y

        # Foot pad
        foot = make_box("foot", 0.12, 0.06, 0.15, metal_dark)
        foot.reparentTo(base_np)
        foot.setPos(foot_x, foot_y, 0)

    # Center column
    column = make_cylinder("column", 0.06, 1.2, 12, metal_dark)
    column.reparentTo(base_np)
    column.setPos(0, 0, 0)

    # === YAW (AZIMUTH) NODE ===
    yaw_np = base_np.attachNewNode("yaw_pivot")
    yaw_np.setPos(0, 0, 1.2)

    # Rotation ring
    ring = make_cylinder("ring", 0.15, 0.08, 16, metal_light)
    ring.reparentTo(yaw_np)
    ring.setPos(0, 0, -0.04)

    # === PITCH (ELEVATION) NODE ===
    pitch_np = yaw_np.attachNewNode("pitch_pivot")
    pitch_np.setPos(0, 0, 0.1)

    # Cradle / receiver assembly
    cradle = make_box("cradle", 0.5, 0.2, 0.15, metal_light)
    cradle.reparentTo(pitch_np)
    cradle.setPos(0, 0.15, 0)

    # Ammo box (left side)
    ammo_box = make_box("ammo_box", 0.15, 0.25, 0.12, (0.2, 0.22, 0.18, 1))
    ammo_box.reparentTo(pitch_np)
    ammo_box.setPos(-0.35, 0.12, 0)

    # === LEFT BARREL ===
    barrel_l_np = pitch_np.attachNewNode("barrel_left")
    barrel_l_np.setPos(-0.1, 0.18, 0)

    # Barrel tube
    barrel_l = make_cylinder("barrel_l_tube", 0.02, 1.5, 10, metal_barrel)
    barrel_l.reparentTo(barrel_l_np)
    barrel_l.setP(-90)  # Point forward (along Y in Panda3D)

    # Barrel jacket (thicker section near receiver)
    jacket_l = make_cylinder("jacket_l", 0.035, 0.6, 10, metal_dark)
    jacket_l.reparentTo(barrel_l_np)
    jacket_l.setP(-90)

    # Flash hider
    flash_l = make_cylinder("flash_l", 0.03, 0.08, 8, metal_dark)
    flash_l.reparentTo(barrel_l_np)
    flash_l.setPos(0, 1.45, 0)
    flash_l.setP(-90)

    # Muzzle point (for effects)
    muzzle_l = barrel_l_np.attachNewNode("muzzle_left")
    muzzle_l.setPos(0, 1.55, 0)

    # === RIGHT BARREL ===
    barrel_r_np = pitch_np.attachNewNode("barrel_right")
    barrel_r_np.setPos(0.1, 0.18, 0)

    barrel_r = make_cylinder("barrel_r_tube", 0.02, 1.5, 10, metal_barrel)
    barrel_r.reparentTo(barrel_r_np)
    barrel_r.setP(-90)

    jacket_r = make_cylinder("jacket_r", 0.035, 0.6, 10, metal_dark)
    jacket_r.reparentTo(barrel_r_np)
    jacket_r.setP(-90)

    flash_r = make_cylinder("flash_r", 0.03, 0.08, 8, metal_dark)
    flash_r.reparentTo(barrel_r_np)
    flash_r.setPos(0, 1.45, 0)
    flash_r.setP(-90)

    muzzle_r = barrel_r_np.attachNewNode("muzzle_right")
    muzzle_r.setPos(0, 1.55, 0)

    # === SCOPE (between barrels, on top of cradle) ===
    scope_color = (0.15, 0.15, 0.14, 1)
    scope_np = pitch_np.attachNewNode("scope")
    scope_np.setPos(0, 0.1, 0.12)  # Centered between barrels, above cradle

    # Main scope tube — points forward along +Y (same as barrels)
    scope_tube = make_cylinder("scope_tube", 0.018, 0.35, 10, scope_color)
    scope_tube.reparentTo(scope_np)
    scope_tube.setP(-90)

    # Objective lens housing (front, slightly wider)
    obj_housing = make_cylinder("scope_obj", 0.024, 0.04, 10, scope_color)
    obj_housing.reparentTo(scope_np)
    obj_housing.setPos(0, 0.32, 0)
    obj_housing.setP(-90)

    # Eyepiece housing (rear, slightly wider)
    eye_housing = make_cylinder("scope_eye", 0.022, 0.04, 10, scope_color)
    eye_housing.reparentTo(scope_np)
    eye_housing.setPos(0, -0.02, 0)
    eye_housing.setP(-90)

    # Scope mount bracket (connects scope to cradle)
    mount_front = make_box("scope_mount_f", 0.03, 0.02, 0.08, metal_dark)
    mount_front.reparentTo(scope_np)
    mount_front.setPos(0, 0.15, -0.06)

    mount_rear = make_box("scope_mount_r", 0.03, 0.02, 0.08, metal_dark)
    mount_rear.reparentTo(scope_np)
    mount_rear.setPos(0, 0.02, -0.06)

    # === HANDLES / GRIPS ===
    grip_l = make_cylinder("grip_l", 0.015, 0.15, 8, metal_dark)
    grip_l.reparentTo(pitch_np)
    grip_l.setPos(-0.2, -0.05, 0)
    grip_l.setP(20)

    grip_r = make_cylinder("grip_r", 0.015, 0.15, 8, metal_dark)
    grip_r.reparentTo(pitch_np)
    grip_r.setPos(0.2, -0.05, 0)
    grip_r.setP(20)

    return {
        "base": base_np,
        "yaw": yaw_np,
        "pitch": pitch_np,
        "barrel_l": barrel_l_np,
        "barrel_r": barrel_r_np,
        "muzzle_l": muzzle_l,
        "muzzle_r": muzzle_r,
    }


def build_environment(parent: NodePath):
    """Build the shooting range environment."""
    # Ground plane
    ground = make_box("ground", 200, 200, 0.1, (0.35, 0.45, 0.25, 1))
    ground.reparentTo(parent)
    ground.setPos(0, 0, -0.05)

    # Horizon trees (simple cone + cylinder)
    import random
    random.seed(42)
    for i in range(60):
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(80, 100)
        x = dist * math.sin(angle)
        y = dist * math.cos(angle)
        height = random.uniform(5, 12)

        # Trunk
        trunk = make_cylinder(f"trunk_{i}", 0.2, height * 0.4, 6,
                             (0.4, 0.25, 0.15, 1))
        trunk.reparentTo(parent)
        trunk.setPos(x, y, 0)

        # Canopy (cone approximated by thin cylinder)
        canopy = make_cylinder(f"canopy_{i}", height * 0.25, height * 0.6, 6,
                              (0.15, 0.4 + random.uniform(-0.1, 0.1), 0.12, 1))
        canopy.reparentTo(parent)
        canopy.setPos(x, y, height * 0.4)

    return ground


def build_target_model(parent: NodePath, target_type: str, radius: float) -> NodePath:
    """Build a target model (simple sphere with wings for aircraft)."""
    color_map = {
        "drone": (0.8, 0.3, 0.1, 1),
        "light_aircraft": (0.2, 0.5, 0.8, 1),
        "helicopter": (0.2, 0.4, 0.2, 1),
        "cruise_missile": (0.6, 0.6, 0.6, 1),
    }
    color = color_map.get(target_type, (1, 0, 0, 1))

    target_np = parent.attachNewNode(f"target_{target_type}")

    # Main body
    body = make_sphere("body", radius, 10, 6, color)
    body.reparentTo(target_np)

    # Wings for aircraft/missile/helicopter types
    if "aircraft" in target_type or "missile" in target_type or "helicopter" in target_type:
        wing = make_box("wing", radius * 3, radius * 0.1, radius * 0.5, color)
        wing.reparentTo(target_np)

    return target_np


def build_training_target(parent: NodePath, **kwargs) -> NodePath:
    """
    Build a static training target: small single-engine light aircraft
    (Cessna-style). Faces south (-Y) toward the turret.
    Wingspan ~11 m, fuselage ~8 m — realistic Cessna 172 proportions.
    """
    plane = parent.attachNewNode("training_target")

    # --- Colors ---
    white = (0.92, 0.92, 0.90, 1)
    blue_stripe = (0.15, 0.25, 0.55, 1)
    dark = (0.20, 0.20, 0.22, 1)
    glass = (0.45, 0.60, 0.75, 0.85)
    red = (0.75, 0.10, 0.10, 1)
    rubber = (0.15, 0.15, 0.15, 1)

    # --- Fuselage (tapered: nose cylinder + main body + tail cone) ---
    # Main fuselage body
    fuse_main = make_cylinder("fuse_main", 0.55, 4.0, 10, white)
    fuse_main.reparentTo(plane)
    fuse_main.setPos(0, -1.0, 0)
    fuse_main.setP(-90)

    # Nose cone (tapers forward)
    nose = make_cylinder("nose", 0.45, 1.2, 10, white)
    nose.reparentTo(plane)
    nose.setPos(0, -2.2, 0)
    nose.setP(-90)

    # Engine cowling (slightly wider at front)
    cowl = make_cylinder("cowl", 0.50, 0.6, 10, dark)
    cowl.reparentTo(plane)
    cowl.setPos(0, -3.2, 0)
    cowl.setP(-90)

    # Spinner / propeller hub
    spinner = make_sphere("spinner", 0.15, 8, 6, dark)
    spinner.reparentTo(plane)
    spinner.setPos(0, -3.9, 0)

    # Propeller blades (2-blade, thin boxes)
    prop_color = (0.25, 0.22, 0.18, 1)
    blade1 = make_box("prop_blade1", 0.12, 0.04, 1.2, prop_color)
    blade1.reparentTo(plane)
    blade1.setPos(0, -3.95, 0)

    blade2 = make_box("prop_blade2", 1.2, 0.04, 0.12, prop_color)
    blade2.reparentTo(plane)
    blade2.setPos(0, -3.95, 0)

    # Tail cone (narrows toward tail)
    tail_cone = make_cylinder("tail_cone", 0.35, 3.0, 8, white)
    tail_cone.reparentTo(plane)
    tail_cone.setPos(0, 3.0, 0.1)
    tail_cone.setP(-90)

    # Blue stripe along fuselage
    stripe = make_box("stripe", 0.56, 6.0, 0.12, blue_stripe)
    stripe.reparentTo(plane)
    stripe.setPos(0, -0.5, 0.15)

    # --- Cockpit / windshield ---
    windshield = make_box("windshield", 0.48, 0.8, 0.35, glass)
    windshield.reparentTo(plane)
    windshield.setPos(0, -1.3, 0.45)
    windshield.setTransparency(TransparencyAttrib.MAlpha)

    # --- Main wings (high-wing, Cessna style) ---
    wing_color = white
    # Left wing
    l_wing = make_box("wing_left", 5.5, 1.2, 0.08, wing_color)
    l_wing.reparentTo(plane)
    l_wing.setPos(-3.0, -0.2, 0.55)

    # Right wing
    r_wing = make_box("wing_right", 5.5, 1.2, 0.08, wing_color)
    r_wing.reparentTo(plane)
    r_wing.setPos(3.0, -0.2, 0.55)

    # Wing struts (connect wing to lower fuselage)
    strut_l = make_box("strut_l", 0.03, 0.8, 0.03, dark)
    strut_l.reparentTo(plane)
    strut_l.setPos(-1.5, -0.2, 0.28)
    strut_l.setR(25)
    strut_l.setSz(4.5)

    strut_r = make_box("strut_r", 0.03, 0.8, 0.03, dark)
    strut_r.reparentTo(plane)
    strut_r.setPos(1.5, -0.2, 0.28)
    strut_r.setR(-25)
    strut_r.setSz(4.5)

    # --- Horizontal stabilizer (tail) ---
    h_stab = make_box("h_stab", 3.6, 0.8, 0.06, wing_color)
    h_stab.reparentTo(plane)
    h_stab.setPos(0, 5.5, 0.3)

    # --- Vertical stabilizer (tail fin) ---
    v_stab = make_box("v_stab", 0.06, 1.0, 1.4, wing_color)
    v_stab.reparentTo(plane)
    v_stab.setPos(0, 5.2, 1.0)

    # Rudder stripe
    rudder_stripe = make_box("rudder_stripe", 0.07, 0.3, 0.5, red)
    rudder_stripe.reparentTo(plane)
    rudder_stripe.setPos(0, 5.7, 1.3)

    # --- Landing gear ---
    # Nose gear
    nose_strut = make_cylinder("nose_strut", 0.03, 0.5, 6, dark)
    nose_strut.reparentTo(plane)
    nose_strut.setPos(0, -2.5, -0.55)

    nose_wheel = make_cylinder("nose_wheel", 0.12, 0.06, 8, rubber)
    nose_wheel.reparentTo(plane)
    nose_wheel.setPos(0, -2.5, -1.05)
    nose_wheel.setR(90)

    # Main gear left
    main_strut_l = make_cylinder("main_strut_l", 0.03, 0.5, 6, dark)
    main_strut_l.reparentTo(plane)
    main_strut_l.setPos(-0.8, 0.0, -0.55)

    main_wheel_l = make_cylinder("main_wheel_l", 0.15, 0.08, 8, rubber)
    main_wheel_l.reparentTo(plane)
    main_wheel_l.setPos(-0.8, 0.0, -1.05)
    main_wheel_l.setR(90)

    # Main gear right
    main_strut_r = make_cylinder("main_strut_r", 0.03, 0.5, 6, dark)
    main_strut_r.reparentTo(plane)
    main_strut_r.setPos(0.8, 0.0, -0.55)

    main_wheel_r = make_cylinder("main_wheel_r", 0.15, 0.08, 8, rubber)
    main_wheel_r.reparentTo(plane)
    main_wheel_r.setPos(0.8, 0.0, -1.05)
    main_wheel_r.setR(90)

    return plane

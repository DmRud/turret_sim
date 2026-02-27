"""
Procedural 3D model generation for the turret simulator.
Creates all geometry programmatically (no external assets needed).
"""

import math
import random as _random
from panda3d.core import (
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomPoints, GeomNode,
    LVector3, LVector4, LPoint3, LColor,
    NodePath, Material, TextureStage, Texture,
    CardMaker, LineSegs,
    TransparencyAttrib,
    PNMImage, PerlinNoise2,
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


def build_sky_dome(parent: NodePath) -> NodePath:
    """
    Build an inverted hemisphere sky dome with a smooth vertical gradient.

    Bottom ring  → horizon haze  (0.75, 0.82, 0.90)
    Top vertex   → zenith blue   (0.35, 0.55, 0.85)

    Rendered in the background bin with no depth write so everything
    draws in front of it.
    """
    segments = 24
    rings = 12
    radius = 2000.0

    # Horizon (bottom of dome) and zenith (top) colours
    hz_r, hz_g, hz_b = 0.78, 0.84, 0.92
    zn_r, zn_g, zn_b = 0.35, 0.55, 0.85

    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("sky_dome", fmt, Geom.UHStatic)

    vertex = GeomVertexWriter(vdata, 'vertex')
    normal = GeomVertexWriter(vdata, 'normal')
    col = GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)

    # Generate hemisphere (phi from 0=top to pi/2=horizon)
    for j in range(rings + 1):
        phi = (math.pi / 2) * j / rings          # 0 → π/2
        t = j / rings                              # 0 (zenith) → 1 (horizon)
        r = hz_r * t + zn_r * (1 - t)
        g = hz_g * t + zn_g * (1 - t)
        b = hz_b * t + zn_b * (1 - t)

        for i in range(segments + 1):
            theta = 2 * math.pi * i / segments
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)

            # Inward-facing normals (we view from inside)
            nx = -math.sin(phi) * math.cos(theta)
            ny = -math.sin(phi) * math.sin(theta)
            nz = -math.cos(phi)

            vertex.addData3(x, y, z)
            normal.addData3(nx, ny, nz)
            col.addData4(r, g, b, 1.0)

    for j in range(rings):
        for i in range(segments):
            p0 = j * (segments + 1) + i
            p1 = p0 + 1
            p2 = p0 + segments + 1
            p3 = p2 + 1
            # Winding order reversed for inside-out sphere
            tris.addVertices(p0, p1, p2)
            tris.addVertices(p1, p3, p2)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("sky_dome")
    node.addGeom(geom)

    sky_np = parent.attachNewNode(node)
    sky_np.setLightOff()
    sky_np.setBin("background", 0)
    sky_np.setDepthWrite(False)
    return sky_np


def build_night_sky_dome(parent: NodePath) -> NodePath:
    """
    Build an inverted hemisphere night sky dome with stars.

    Bottom ring  → dark horizon      (0.03, 0.03, 0.06)
    Top vertex   → deep night blue   (0.01, 0.01, 0.04)

    Stars are rendered as small bright points scattered across the dome.
    """
    segments = 24
    rings = 12
    radius = 2000.0

    # Horizon and zenith colours (night)
    hz_r, hz_g, hz_b = 0.04, 0.04, 0.08
    zn_r, zn_g, zn_b = 0.01, 0.01, 0.04

    fmt = GeomVertexFormat.getV3n3c4()
    vdata = GeomVertexData("night_sky_dome", fmt, Geom.UHStatic)

    vertex = GeomVertexWriter(vdata, 'vertex')
    normal = GeomVertexWriter(vdata, 'normal')
    col = GeomVertexWriter(vdata, 'color')
    tris = GeomTriangles(Geom.UHStatic)

    for j in range(rings + 1):
        phi = (math.pi / 2) * j / rings
        t = j / rings
        r = hz_r * t + zn_r * (1 - t)
        g = hz_g * t + zn_g * (1 - t)
        b = hz_b * t + zn_b * (1 - t)

        for i in range(segments + 1):
            theta = 2 * math.pi * i / segments
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)

            nx = -math.sin(phi) * math.cos(theta)
            ny = -math.sin(phi) * math.sin(theta)
            nz = -math.cos(phi)

            vertex.addData3(x, y, z)
            normal.addData3(nx, ny, nz)
            col.addData4(r, g, b, 1.0)

    for j in range(rings):
        for i in range(segments):
            p0 = j * (segments + 1) + i
            p1 = p0 + 1
            p2 = p0 + segments + 1
            p3 = p2 + 1
            tris.addVertices(p0, p1, p2)
            tris.addVertices(p1, p3, p2)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    gnode = GeomNode("night_sky_dome")
    gnode.addGeom(geom)

    sky_np = parent.attachNewNode(gnode)
    sky_np.setLightOff()
    sky_np.setBin("background", 0)
    sky_np.setDepthWrite(False)

    # --- Stars ---
    rng = _random.Random(42)
    star_count = 600
    star_radius = radius * 0.99  # slightly inside dome

    star_vdata = GeomVertexData("stars", GeomVertexFormat.getV3c4(), Geom.UHStatic)
    star_vertex = GeomVertexWriter(star_vdata, 'vertex')
    star_col = GeomVertexWriter(star_vdata, 'color')
    star_pts = GeomPoints(Geom.UHStatic)

    for k in range(star_count):
        # Random position on upper hemisphere
        sphi = rng.uniform(0, math.pi / 2 * 0.92)  # avoid horizon band
        stheta = rng.uniform(0, 2 * math.pi)
        sx = star_radius * math.sin(sphi) * math.cos(stheta)
        sy = star_radius * math.sin(sphi) * math.sin(stheta)
        sz = star_radius * math.cos(sphi)
        star_vertex.addData3(sx, sy, sz)

        # Random brightness and slight color variation
        brightness = rng.uniform(0.5, 1.0)
        tint = rng.random()
        if tint < 0.7:
            # White
            star_col.addData4(brightness, brightness, brightness, 1.0)
        elif tint < 0.85:
            # Warm (slightly orange/yellow)
            star_col.addData4(brightness, brightness * 0.85, brightness * 0.6, 1.0)
        else:
            # Cool (slightly blue)
            star_col.addData4(brightness * 0.7, brightness * 0.8, brightness, 1.0)

        star_pts.addVertex(k)

    star_geom = Geom(star_vdata)
    star_geom.addPrimitive(star_pts)
    star_node = GeomNode("stars")
    star_node.addGeom(star_geom)

    stars_np = sky_np.attachNewNode(star_node)
    stars_np.setLightOff()
    stars_np.setRenderModeThickness(2)
    stars_np.setBin("background", 1)
    stars_np.setDepthWrite(False)

    return sky_np


def build_cloud_layer(parent: NodePath) -> NodePath:
    """
    Build a layer of 8 procedural cloud quads at high altitude.

    Each cloud is a semi-transparent textured quad generated with
    Perlin noise, randomly placed in a 400 m ring at 500-800 m altitude.
    """
    cloud_root = parent.attachNewNode("cloud_layer")

    rng = _random.Random(99)
    noise = PerlinNoise2(4, 4, 256, rng.randint(0, 9999))

    for idx in range(8):
        # Random placement
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(60, 400)
        cx = dist * math.cos(angle)
        cy = dist * math.sin(angle)
        alt = rng.uniform(500, 800)
        size = rng.uniform(60, 160)

        # Generate cloud texture (PNMImage RGBA)
        res = 64
        img = PNMImage(res, res, 4)       # 4-channel RGBA
        img.addAlpha()                     # ensure alpha channel exists
        for py in range(res):
            for px in range(res):
                # Normalised coords -1..1
                u = (px / (res - 1)) * 2 - 1
                v = (py / (res - 1)) * 2 - 1
                # Falloff from centre (elliptical, softer edges)
                d2 = u * u + v * v
                falloff = max(0.0, 1.0 - d2)
                # Perlin noise for puffiness
                n = noise(px / res * 4 + idx * 7.3, py / res * 4 + idx * 3.1)
                n = (n + 1.0) * 0.5   # map -1..1 → 0..1
                alpha = falloff * n
                alpha = min(1.0, alpha * 2.2)  # boost
                alpha *= 0.55                   # overall translucency
                img.setXelA(px, py, 1.0, 1.0, 1.0, alpha)

        tex = Texture(f"cloud_tex_{idx}")
        tex.load(img)
        tex.setWrapU(Texture.WMClamp)
        tex.setWrapV(Texture.WMClamp)

        # Build quad
        cm = CardMaker(f"cloud_{idx}")
        hs = size / 2
        cm.setFrame(-hs, hs, -hs, hs)
        card = cloud_root.attachNewNode(cm.generate())
        card.setTexture(tex)
        card.setTransparency(TransparencyAttrib.MAlpha)
        card.setLightOff()
        card.setBin("fixed", 5)
        card.setDepthWrite(False)

        # Lay flat and position
        card.setP(-90)
        card.setPos(cx, cy, alt)
        # Slight random rotation
        card.setH(rng.uniform(0, 360))

    return cloud_root


def _generate_ground_texture() -> Texture:
    """Generate a 512x512 procedural grass/dirt ground texture using Perlin noise."""
    res = 512
    img = PNMImage(res, res, 3)

    # Two Perlin noise layers with different frequencies
    noise_large = PerlinNoise2(6, 6, 256, 42)
    noise_fine = PerlinNoise2(32, 32, 256, 137)

    # Base grass-brown colour
    base_r, base_g, base_b = 0.32, 0.42, 0.22

    for py in range(res):
        for px in range(res):
            u = px / res
            v = py / res
            # Large-scale patches (lighter / darker green-brown)
            n1 = noise_large(u * 6, v * 6)        # -1..1
            n1 = n1 * 0.12                          # subtle shift
            # Fine grain
            n2 = noise_fine(u * 32, v * 32)
            n2 = n2 * 0.06

            r = max(0.0, min(1.0, base_r + n1 * 0.8 + n2 * 0.5))
            g = max(0.0, min(1.0, base_g + n1 + n2))
            b = max(0.0, min(1.0, base_b + n1 * 0.6 + n2 * 0.4))
            img.setXel(px, py, r, g, b)

    tex = Texture("ground_tex")
    tex.load(img)
    tex.setWrapU(Texture.WMRepeat)
    tex.setWrapV(Texture.WMRepeat)
    tex.setMinfilter(Texture.FTLinearMipmapLinear)
    tex.setMagfilter(Texture.FTLinear)
    return tex


def _generate_grass_texture() -> Texture:
    """Generate a small grass-blade texture (RGBA) for billboard quads."""
    w, h = 32, 64
    img = PNMImage(w, h, 4)
    img.addAlpha()
    img.fill(0.0, 0.0, 0.0)
    # Fill with transparent
    for py in range(h):
        for px in range(w):
            img.setAlpha(px, py, 0.0)

    # Draw 3 triangular blades
    rng = _random.Random(77)
    for blade in range(3):
        cx = rng.randint(6, w - 7)
        bw = rng.randint(3, 6)       # blade half-width at base
        green = 0.3 + rng.random() * 0.3
        for py in range(h):
            t = py / h  # 0=bottom, 1=top
            half_w = bw * (1.0 - t * 0.9)  # narrows toward top
            for px in range(max(0, int(cx - half_w)), min(w, int(cx + half_w) + 1)):
                g_val = green + 0.15 * (1 - t)
                img.setXelA(px, py, 0.15, g_val, 0.08, 0.85)

    tex = Texture("grass_blade")
    tex.load(img)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    return tex


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
    """Build the shooting range environment with textured ground, trees, bushes, and grass."""

    # ── Textured ground plane ────────────────────────────────────
    ground_tex = _generate_ground_texture()

    # Use a simple box; apply UV-tiled texture
    ground = make_box("ground", 400, 400, 0.1, (1.0, 1.0, 1.0, 1))
    ground.reparentTo(parent)
    ground.setPos(0, 0, -0.05)
    ground.setTexture(ground_tex)
    ground.setTexScale(TextureStage.getDefault(), 30, 30)

    rng = _random.Random(42)

    # ── Trees (fuller canopy: 2-3 stacked spheres) ───────────────
    # Distant ring: 80–100 m
    for i in range(50):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(80, 100)
        _build_tree(parent, dist * math.sin(angle), dist * math.cos(angle),
                    rng.uniform(8, 14), rng, f"tree_far_{i}")

    # Mid-range ring: 40–70 m
    for i in range(25):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(40, 70)
        _build_tree(parent, dist * math.sin(angle), dist * math.cos(angle),
                    rng.uniform(6, 11), rng, f"tree_mid_{i}")

    # ── Bushes (small green spheres, 20-55 m) ───────────────────
    for i in range(30):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(20, 55)
        bx = dist * math.sin(angle)
        by = dist * math.cos(angle)
        bh = rng.uniform(0.8, 1.8)
        bw = rng.uniform(1.0, 2.2)
        green = 0.30 + rng.uniform(-0.08, 0.08)
        bush = make_sphere(f"bush_{i}", bw / 2, 8, 5,
                           (0.12, green, 0.10, 1))
        bush.reparentTo(parent)
        bush.setPos(bx, by, bh * 0.4)
        bush.setSz(bh / bw)

    # ── Grass patches (crossed billboard quads near turret) ──────
    grass_tex = _generate_grass_texture()
    grass_root = parent.attachNewNode("grass")

    for i in range(250):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(1.5, 35)
        gx = dist * math.sin(angle)
        gy = dist * math.cos(angle)
        gh = rng.uniform(0.3, 0.65)
        gw = gh * rng.uniform(0.3, 0.5)

        # Two crossed quads (X-shape)
        for rot in (0, 90):
            cm = CardMaker(f"grass_{i}_{rot}")
            cm.setFrame(-gw / 2, gw / 2, 0, gh)
            card = grass_root.attachNewNode(cm.generate())
            card.setTexture(grass_tex)
            card.setTransparency(TransparencyAttrib.MDual)
            card.setPos(gx, gy, 0)
            card.setH(rng.uniform(0, 360) + rot)
            # Slight green tint variation
            tint = 0.8 + rng.uniform(-0.15, 0.15)
            card.setColor(tint, 1.0, tint, 1.0)

    grass_root.setLightOff()
    grass_root.setDepthWrite(True)
    grass_root.setBin("transparent", 0)

    return ground


def _build_tree(parent, x, y, height, rng, name):
    """Build a single tree with trunk + 2-3 stacked canopy spheres."""
    trunk_h = height * 0.35
    trunk_r = 0.15 + height * 0.015
    bark = (0.35 + rng.uniform(-0.05, 0.05),
            0.22 + rng.uniform(-0.04, 0.04),
            0.12, 1)

    trunk = make_cylinder(f"{name}_trunk", trunk_r, trunk_h, 6, bark)
    trunk.reparentTo(parent)
    trunk.setPos(x, y, 0)

    # 2-3 canopy spheres stacked with overlap
    n_layers = rng.choice([2, 2, 3])
    canopy_r = height * 0.22
    green_base = 0.35 + rng.uniform(-0.08, 0.08)
    for layer in range(n_layers):
        z = trunk_h + canopy_r * 0.7 * layer
        layer_r = canopy_r * (1.0 - layer * 0.15)
        g = green_base + layer * 0.05
        canopy = make_sphere(f"{name}_canopy_{layer}",
                             layer_r, 8, 5,
                             (0.10, g, 0.08, 1))
        canopy.reparentTo(parent)
        canopy.setPos(x + rng.uniform(-0.3, 0.3),
                      y + rng.uniform(-0.3, 0.3),
                      z)


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
    Load the Shahed-136 (Geranium-2) drone model as the training target.
    Falls back to a simple procedural placeholder if the model file is missing.

    The EGG model is in centimetres (wingspan ~250 cm, length ~350 cm).
    We scale by 0.01 to convert to metres, then orient so the drone
    faces south (-Y) toward the turret (nose along -Y in ENU).
    """
    import os
    asset_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             "assets", "shahed")
    egg_path = os.path.join(asset_dir, "Geranium2.egg")

    wrapper = parent.attachNewNode("training_target")

    if os.path.isfile(egg_path):
        from panda3d.core import Filename
        import builtins

        _loader = builtins.loader  # Panda3D global set by ShowBase

        model = _loader.loadModel(Filename.fromOsSpecific(egg_path))
        model.reparentTo(wrapper)

        # cm → m
        model.setScale(0.01)

        # The model's Z axis is the fuselage length.
        # Rotate so model's +Z becomes -Y in Panda (nose pointing south).
        # Model: wingspan on X, short on Y (thickness), length on Z.
        # We want length along Y-axis (north/south) with nose toward -Y.
        model.setP(90)    # Tilt +Z forward → now length is along +Y
        model.setH(180)   # Flip 180° so nose faces -Y (south toward turret)

        # Apply base-colour texture
        tex_path = os.path.join(asset_dir, "textures", "Geranium2_BaseColor.png")
        if os.path.isfile(tex_path):
            tex = _loader.loadTexture(Filename.fromOsSpecific(tex_path))
            model.setTexture(tex, 1)
    else:
        # Fallback: simple grey delta-wing shape
        body = make_cylinder("body", 0.15, 2.5, 8, (0.45, 0.45, 0.42, 1))
        body.reparentTo(wrapper)
        body.setP(-90)

        wing = make_box("wing", 2.5, 0.6, 0.04, (0.45, 0.45, 0.42, 1))
        wing.reparentTo(wrapper)
        wing.setPos(0, 0.3, 0)

    return wrapper

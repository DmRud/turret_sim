"""
Turret Simulator - Main Application
Panda3D-based 3D desktop application.

Controls:
  LMB / MMB drag : Orbit camera
  Scroll          : Zoom camera
  Arrow keys / WASD : Rotate turret (simultaneous X+Y)
  Space           : Fire
  R               : Reload
  Enter           : Start game / Next round
  T               : Training mode (static target at 700 m)
  C               : Toggle first-person / orbit camera
  V               : Toggle scope thermal imaging
  N               : Toggle day/night mode
  ]               : Toggle debug panel
  Esc             : Quit
"""

import sys
import math
import random
import numpy as np

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.gui.OnscreenText import OnscreenText

from panda3d.core import (
    LVector3, LVector4, LPoint3, LColor,
    NodePath, GeomNode, LineSegs,
    AmbientLight, DirectionalLight, PointLight, Fog,
    TextNode, CardMaker,
    WindowProperties, FrameBufferProperties,
    GraphicsOutput, GraphicsPipe, Texture,
    DisplayRegion, Camera, Lens, PerspectiveLens,
    TransparencyAttrib, ColorBlendAttrib,
    AntialiasAttrib, RenderModeAttrib,
    KeyboardButton, BitMask32,
    Shader,
    loadPrcFileData,
)

# Configure Panda3D before importing ShowBase internals
loadPrcFileData("", """
    window-title Turret Simulator - Browning M2 Twin Mount
    win-size 1280 720
    show-frame-rate-meter 1
    sync-video 0
    textures-power-2 none
""")

from rendering.models import (
    build_turret_model, build_environment, build_target_model,
    build_training_target, build_sky_dome, build_night_sky_dome, build_cloud_layer,
    make_sphere, make_cylinder, make_box,
)
from game.manager import GameManager, GameState
from api.rest_server import TurretAPI
from api.ws_server import EventBroadcaster


class TurretSimApp(ShowBase):
    """Main application class."""

    def __init__(self):
        ShowBase.__init__(self)

        print("\n" + "="*60)
        print("  TURRET SIMULATOR - Browning M2 .50 Cal Twin Mount")
        print("="*60)

        # === GAME MANAGER ===
        self.game_mgr = GameManager()
        self.game_mgr.add_event_listener(self._on_game_event)

        # === SERVERS ===
        print("\nStarting servers...")
        self.api_server = TurretAPI(port=8420)
        self.api_server.bind(
            turret=self.game_mgr.turret,
            target_manager=self.game_mgr.target_manager,
            game_manager=self.game_mgr,
            ballistics_engine=self.game_mgr.engine,
        )
        self.api_server.start()

        self.ws_server = EventBroadcaster(port=8421)
        self.ws_server.start()

        # === SCENE SETUP ===
        self._setup_scene()
        self._setup_lights()
        self._setup_camera()
        self._setup_turret()
        self._setup_hud()
        self._setup_monocular()
        self._setup_scope_debug()

        # === INPUT ===
        self._setup_controls()

        # === GAME STATE ===
        self.target_np = None
        self.tracer_nodes = []
        self.muzzle_flash_timer = 0
        self.next_barrel = 0  # Alternate L/R

        # === MAIN LOOP ===
        self.taskMgr.add(self._update, "main_update")

        print("\n" + "-"*60)
        print("  Controls:")
        print("    Arrow keys / WASD : Rotate turret")
        print("    Space             : Fire")
        print("    R                 : Reload")
        print("    Enter             : Start game / Next round")
        print("    T                 : Training mode (static target)")
        print("    C                 : Toggle first-person / orbit camera")
        print("    V                 : Toggle scope thermal imaging")
        print("    LMB / MMB drag    : Orbit camera")
        print("    Scroll            : Zoom camera")
        print("    ]                 : Toggle debug panel")
        print("    ESC               : Quit")
        print("-"*60)
        print(f"\n  REST API:     http://localhost:8420")
        print(f"  WebSocket:    ws://localhost:8421")
        print(f"\n  Press ENTER to start | T for training")
        print("="*60 + "\n")

    # =========================================================
    # SCENE SETUP
    # =========================================================

    def _setup_scene(self):
        """Build the 3D environment."""
        # --- Day / Night state ---
        self._is_night = True  # default: night

        # --- Day sky ---
        self._day_sky = build_sky_dome(self.render)
        self._day_sky.hide()

        # --- Night sky (with stars) ---
        self._night_sky = build_night_sky_dome(self.render)

        # Environment (ground, trees, bushes, grass)
        self.env_root = self.render.attachNewNode("environment")
        build_environment(self.env_root)

        # Cloud layer (semi-transparent quads at altitude)
        self.cloud_root = build_cloud_layer(self.render)

        # Fog node — stored so we can adjust color per mode
        self._scene_fog = Fog("scene_fog")
        self.render.setFog(self._scene_fog)

        # Enable antialiasing
        self.render.setAntialias(AntialiasAttrib.MAuto)

        # Apply initial mode
        self._apply_day_night()

    def _setup_lights(self):
        """Set up scene lighting (values adjusted by day/night toggle)."""
        # Ambient
        self._ambient_light = AmbientLight('ambient')
        self._ambient_np = self.render.attachNewNode(self._ambient_light)
        self.render.setLight(self._ambient_np)

        # Sun / Moon (directional)
        self._sun_light = DirectionalLight('sun')
        self._sun_np = self.render.attachNewNode(self._sun_light)
        self._sun_np.setHpr(45, -45, 0)
        self.render.setLight(self._sun_np)

        # Fill light
        self._fill_light = DirectionalLight('fill')
        self._fill_np = self.render.attachNewNode(self._fill_light)
        self._fill_np.setHpr(-135, -30, 0)
        self.render.setLight(self._fill_np)

        # Apply colours matching current day/night state
        self._apply_day_night_lights()

    def _apply_day_night(self):
        """Apply full day/night visual state (sky, fog, background, clouds)."""
        if self._is_night:
            self.setBackgroundColor(0.02, 0.02, 0.05, 1)
            self._day_sky.hide()
            self._night_sky.show()
            self._scene_fog.setColor(0.02, 0.02, 0.05)
            self._scene_fog.setExpDensity(0.004)
            self.cloud_root.hide()
        else:
            self.setBackgroundColor(0.78, 0.84, 0.92, 1)
            self._day_sky.show()
            self._night_sky.hide()
            self._scene_fog.setColor(0.75, 0.82, 0.90)
            self._scene_fog.setExpDensity(0.006)
            self.cloud_root.show()

        # Update lights if they exist
        if hasattr(self, '_ambient_light'):
            self._apply_day_night_lights()

    def _apply_day_night_lights(self):
        """Set light colours for current day/night mode."""
        if self._is_night:
            self._ambient_light.setColor(LVector4(0.06, 0.06, 0.10, 1))
            self._sun_light.setColor(LVector4(0.10, 0.12, 0.18, 1))
            self._fill_light.setColor(LVector4(0.04, 0.05, 0.08, 1))
        else:
            self._ambient_light.setColor(LVector4(0.3, 0.3, 0.35, 1))
            self._sun_light.setColor(LVector4(1.0, 0.95, 0.85, 1))
            self._fill_light.setColor(LVector4(0.3, 0.35, 0.4, 1))

    def _toggle_day_night(self):
        """Switch between day and night modes."""
        self._is_night = not self._is_night
        self._apply_day_night()

        # Update the DevTools button if it exists
        if hasattr(self, '_debug_btns') and "night_mode" in self._debug_btns:
            btn = self._debug_btns["night_mode"]
            self.debug_flags["night_mode"] = self._is_night

            BTN_OFF = (0.20, 0.20, 0.20, 1)
            BTN_ON = (0.14, 0.50, 0.24, 1)
            btn["frameColor"] = BTN_ON if self._is_night else BTN_OFF
            btn["text_fg"] = (0.95, 0.95, 0.95, 1) if self._is_night else (0.55, 0.55, 0.55, 1)

            indicator = btn.getPythonTag("indicator")
            if indicator:
                indicator.setText("ON" if self._is_night else "OFF")
                indicator.setFg((0.3, 1, 0.4, 1) if self._is_night else (0.55, 0.55, 0.55, 1))

    def _setup_camera(self):
        """Set up orbit camera."""
        self.disableMouse()

        self.cam_distance = 8.0
        self.cam_heading = 30.0
        self.cam_pitch = -25.0
        self.cam_target = LPoint3(0, 0, 1.2)

        # Camera mode: "orbit" (default) or "first_person"
        self.cam_mode = "orbit"

        # First-person camera node — parented to turret pitch so it
        # follows yaw + elevation automatically (same approach as scope cam).
        # Created later in _setup_turret once turret_parts exists.
        self._fp_cam_np = None

        self._update_camera()

        # Mouse state
        self._mouse_dragging = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0

    def _setup_fp_camera(self):
        """Attach a first-person camera node to the turret pitch pivot.

        Position: slightly behind the receiver, at operator eye-height,
        looking along the barrels (same direction as the scope).
        """
        self._fp_cam_np = self.turret_parts["pitch"].attachNewNode("fp_cam_anchor")
        # Operator stands behind turret, eyes ~0.4 m above pivot, ~0.3 m back
        self._fp_cam_np.setPos(0, -0.35, 0.30)

    def _toggle_camera_mode(self):
        """Switch between orbit and first-person camera modes."""
        if self.cam_mode == "orbit":
            self.cam_mode = "first_person"
            # Wider FOV for immersive first-person, closer near clip for barrel
            lens = self.cam.node().getLens()
            lens.setFov(70)
            lens.setNearFar(0.05, 10000)
            # Hide system cursor and show FP crosshair
            props = WindowProperties()
            props.setCursorHidden(True)
            self.win.requestProperties(props)
            self._fp_crosshair.show()
            self._mouse_dragging = False
            # Center mouse so first frame has no jump
            cx = self.win.getProperties().getXSize() // 2
            cy = self.win.getProperties().getYSize() // 2
            self.win.movePointer(0, cx, cy)
        else:
            self.cam_mode = "orbit"
            # Restore default lens for orbit view
            lens = self.cam.node().getLens()
            lens.setFov(30)
            lens.setNearFar(1.0, 100000)
            # Show system cursor and hide FP crosshair
            props = WindowProperties()
            props.setCursorHidden(False)
            self.win.requestProperties(props)
            self._fp_crosshair.hide()
            # Restore orbit camera so transition is instant
            self._update_orbit_camera()

    def _update_camera(self):
        """Update camera each frame based on current mode."""
        if self.cam_mode == "first_person" and self._fp_cam_np is not None:
            self._update_fp_camera()
        else:
            self._update_orbit_camera()

    def _update_orbit_camera(self):
        """Position camera based on orbit parameters."""
        h_rad = math.radians(self.cam_heading)
        p_rad = math.radians(self.cam_pitch)

        x = self.cam_distance * math.cos(p_rad) * math.sin(h_rad)
        y = self.cam_distance * math.cos(p_rad) * math.cos(h_rad)
        z = self.cam_distance * math.sin(-p_rad)

        cam_pos = self.cam_target + LVector3(x, y, z)
        # Keep camera above ground
        if cam_pos.getZ() < 0.3:
            cam_pos.setZ(0.3)
        self.camera.setPos(cam_pos)
        self.camera.lookAt(self.cam_target)

    def _update_fp_camera(self):
        """First-person: camera follows turret yaw/elevation from operator position."""
        # Get world-space position and orientation of the FP anchor
        world_pos = self._fp_cam_np.getPos(self.render)
        self.camera.setPos(world_pos)

        # Look direction = along barrels (pitch node's local +Y in world)
        mat = self.turret_parts["pitch"].getMat(self.render)
        forward = LVector3(mat.getRow3(1))  # local Y = forward
        look_at = world_pos + forward * 100
        self.camera.lookAt(look_at)

    def _setup_turret(self):
        """Build and set up turret model."""
        self.turret_root = self.render.attachNewNode("turret_root")
        self.turret_parts = build_turret_model(self.turret_root)

        # First-person camera anchor (must be after turret_parts exists)
        self._setup_fp_camera()

        # Muzzle flash sprites (billboard quads)
        self.flash_l = self._make_flash_sprite(self.turret_parts["muzzle_l"])
        self.flash_r = self._make_flash_sprite(self.turret_parts["muzzle_r"])
        self.flash_l.hide()
        self.flash_r.hide()

    def _make_flash_sprite(self, parent_np):
        """Create a muzzle flash billboard."""
        cm = CardMaker("flash")
        cm.setFrame(-0.15, 0.15, -0.15, 0.15)
        flash = parent_np.attachNewNode(cm.generate())
        flash.setBillboardPointEye()
        flash.setColor(1, 0.9, 0.3, 1)
        flash.setTransparency(TransparencyAttrib.MAlpha)
        flash.setLightOff()
        flash.setBin("fixed", 10)
        return flash

    # =========================================================
    # HUD
    # =========================================================

    def _setup_hud(self):
        """Create HUD overlay text."""
        self.hud_texts = {}

        def add_text(name, pos, align=TextNode.ALeft, scale=0.045):
            t = OnscreenText(
                text="", pos=pos, scale=scale,
                fg=(1, 1, 1, 1), shadow=(0, 0, 0, 0.8),
                align=align, mayChange=True,
                parent=self.aspect2d,
            )
            self.hud_texts[name] = t
            return t

        # Top left - game state
        add_text("game_state", (-1.7, 0.92), scale=0.06)
        add_text("round_info", (-1.7, 0.85))
        add_text("countdown", (0, 0.5), TextNode.ACenter, 0.15)

        # Top right - turret status
        add_text("turret_state", (1.7, 0.92), TextNode.ARight)
        add_text("ammo", (1.7, 0.85), TextNode.ARight)
        add_text("heat", (1.7, 0.78), TextNode.ARight)
        add_text("orientation", (1.7, 0.71), TextNode.ARight)

        # Bottom right - target info
        add_text("target_info", (1.7, -0.68), TextNode.ARight)
        add_text("target_dist", (1.7, -0.75), TextNode.ARight)
        add_text("target_alt", (1.7, -0.82), TextNode.ARight)

        # Bottom right - weather (below target info)
        add_text("weather", (1.7, -0.89), TextNode.ARight, 0.035)
        add_text("wind", (1.7, -0.94), TextNode.ARight, 0.035)

        # Center - hit/miss notifications
        add_text("notification", (0, 0.2), TextNode.ACenter, 0.1)

        # Bottom center - stats
        add_text("stats", (0, -0.9), TextNode.ACenter, 0.04)

        # First-person crosshair (centered, hidden by default)
        self._fp_crosshair = OnscreenText(
            text="+", pos=(0, 0), scale=0.07,
            fg=(0, 1, 0, 0.9), shadow=(0, 0, 0, 0.5),
            align=TextNode.ACenter,
            parent=self.aspect2d,
            mayChange=False,
        )
        self._fp_crosshair.setBin("fixed", 20)
        self._fp_crosshair.hide()

        # Camera mode indicator (top center)
        add_text("cam_mode", (0, 0.92), TextNode.ACenter, 0.035)

    def _update_hud(self):
        """Update HUD text every frame."""
        gm = self.game_mgr
        turret = gm.turret
        texts = self.hud_texts

        # Game state
        state_text = {
            GameState.MENU: "Press ENTER to start | T for training",
            GameState.ROUND_START: "Get ready...",
            GameState.PLAYING: "ENGAGE!",
            GameState.TARGET_HIT: "TARGET DESTROYED!",
            GameState.TARGET_ESCAPED: "Target escaped...",
            GameState.ROUND_END: "Press ENTER for next round",
            GameState.GAME_OVER: "GAME OVER",
            GameState.TRAINING: f"TRAINING — {int(gm.training_distance)}m",
            GameState.TRAINING_RESPAWN: "Target respawning...",
        }
        texts["game_state"].setText(state_text.get(gm.state, ""))

        # Round info
        if gm.training_mode:
            texts["round_info"].setText(f"Hits: {gm.training_hits}")
        else:
            texts["round_info"].setText(f"Round {gm.round_number}")

        # Countdown
        if gm.state == GameState.ROUND_START and gm.countdown > 0:
            texts["countdown"].setText(f"{int(gm.countdown) + 1}")
        else:
            texts["countdown"].setText("")

        # Turret / target / weather — only update HUD text if panel is hidden
        # (when panel is visible, _update_devtools handles this data)
        if not self._debug_panel_visible:
            texts["turret_state"].setText(
                f"Turret: {turret.state.value.upper()}")
            texts["ammo"].setText(
                f"Ammo: {turret.ammo_remaining}/{turret.config.belt_capacity}")

            heat_pct = (turret.heat_level
                        / turret.config.overheat_threshold * 100)
            heat_bar = ("#" * int(heat_pct / 5)
                        + "." * (20 - int(heat_pct / 5)))
            texts["heat"].setText(f"Heat: [{heat_bar}] {heat_pct:.0f}%")

            az_deg = np.degrees(turret.azimuth)
            el_deg = np.degrees(turret.elevation)
            texts["orientation"].setText(
                f"Az: {az_deg:.1f}\u00b0 El: {el_deg:.1f}\u00b0")

            w = gm.weather
            texts["weather"].setText(
                f"Temp: {w.temperature_c:.0f}\u00b0C | "
                f"Press: {w.pressure_hpa:.0f}hPa | "
                f"Humid: {w.humidity_pct:.0f}%")
            texts["wind"].setText(
                f"Wind: {w.wind_speed_mps:.1f}m/s "
                f"from {w.wind_direction_deg:.0f}\u00b0")

        # Target info (always update — shown on right side of HUD)
        if gm.current_target and gm.current_target.alive:
            tgt = gm.current_target
            bearing_rad, elev_rad = tgt.get_bearing_elevation()
            texts["target_info"].setText(
                f"Target: {tgt.profile.name} | Speed: {tgt.speed:.0f} m/s")
            texts["target_dist"].setText(
                f"Range: {tgt.range_from_origin:.0f}m | "
                f"Bearing: {np.degrees(bearing_rad):.1f}\u00b0 | "
                f"Elev: {np.degrees(elev_rad):.1f}\u00b0")
            texts["target_alt"].setText(
                f"Altitude: {tgt.altitude:.0f}m | "
                f"Ground range: {tgt.horizontal_range:.0f}m")
        else:
            texts["target_info"].setText("")
            texts["target_dist"].setText("")
            texts["target_alt"].setText("")

        # Notification
        if gm.state == GameState.TARGET_HIT:
            texts["notification"].setText("HIT!")
            texts["notification"].setFg((0, 1, 0, 1))
        elif gm.state == GameState.TARGET_ESCAPED:
            texts["notification"].setText("MISS")
            texts["notification"].setFg((1, 0.3, 0.3, 1))
        else:
            texts["notification"].setText("")

        # Stats
        s = gm.stats
        texts["stats"].setText(
            f"Hits: {s.targets_hit} | Missed: {s.targets_missed} | "
            f"Hit Rate: {s.hit_rate:.0f}% | Ammo Used: {s.total_ammo_used}")

        # Camera mode indicator
        if self.cam_mode == "first_person":
            texts["cam_mode"].setText("FIRST PERSON  [C] to switch")
            texts["cam_mode"].setFg((0.3, 1, 0.4, 0.8))
        else:
            texts["cam_mode"].setText("")

    # =========================================================
    # MONOCULAR (PIP)
    # =========================================================

    def _setup_monocular(self):
        """Create picture-in-picture monocular view."""
        # Create an offscreen buffer.  makeTextureBuffer auto-creates a
        # DisplayRegion that clones the main camera — which is exactly
        # the bug (scope inherits orbit camera movement).
        # Instead we deactivate that default DR and add our own.
        self.scope_buffer = self.win.makeTextureBuffer(
            "scope", 256, 256)
        self.scope_buffer.setSort(-100)
        self.scope_buffer.setClearColorActive(True)
        self.scope_buffer.setClearColor(LColor(0.78, 0.84, 0.92, 1))

        # Deactivate every pre-made DisplayRegion (except the overlay
        # which lives at index 0 and cannot be removed).
        for i in range(self.scope_buffer.getNumDisplayRegions()):
            dr = self.scope_buffer.getDisplayRegion(i)
            dr.setActive(False)

        # Build scope camera as a child of the turret's pitch node so it
        # physically follows both yaw and elevation — just like the real scope.
        # This replaces manual setPos/setHpr in _update_scope_camera.
        scope_lens = PerspectiveLens()
        scope_lens.setFov(5)  # Narrow FOV = zoom
        scope_lens.setNearFar(0.1, 10000)

        scope_cam_node = Camera("scope_cam")
        scope_cam_node.setLens(scope_lens)
        # Scope camera only sees objects on bit 0 (skip bit 1 = scope model)
        scope_cam_node.setCameraMask(BitMask32.bit(0))

        # Attach to pitch_np — same parent as the physical scope model.
        # Local offset (0, 0.1, 0.12) matches the scope node position.
        self.scope_cam = self.turret_parts["pitch"].attachNewNode(scope_cam_node)
        self.scope_cam.setPos(0, 0.1, 0.12)

        # Hide the physical scope model from the scope camera so the
        # camera (which sits inside the scope tube) doesn't see its own
        # geometry as a dark blob.  The scope node keeps bit 1 only,
        # so the main camera (default mask = all bits) still renders it.
        scope_node = self.turret_parts["pitch"].find("**/scope")
        if not scope_node.isEmpty():
            scope_node.hide(BitMask32.bit(0))

        # Our own DisplayRegion tied to the independent scope camera
        dr = self.scope_buffer.makeDisplayRegion()
        dr.setCamera(self.scope_cam)

        # Display the scope texture as PIP
        self.scope_texture = self.scope_buffer.getTexture()

        # Create a card to show the scope view
        cm = CardMaker("scope_display")
        cm.setFrame(-0.45, -0.05, -0.95, -0.55)  # Bottom-left corner
        self.scope_card = self.aspect2d.attachNewNode(cm.generate())
        self.scope_card.setTexture(self.scope_texture)

        # Scope border
        border = CardMaker("scope_border")
        border.setFrame(-0.46, -0.04, -0.96, -0.54)
        border_np = self.aspect2d.attachNewNode(border.generate())
        border_np.setColor(0.1, 0.1, 0.1, 1)
        border_np.setBin("fixed", 0)
        self.scope_card.setBin("fixed", 1)

        # Crosshair
        self._scope_crosshair = OnscreenText(
            text="+", pos=(-0.25, -0.77), scale=0.06,
            fg=(0, 1, 0, 0.8), shadow=(0, 0, 0, 0),
            align=TextNode.ACenter,
            parent=self.aspect2d,
        )
        self._scope_crosshair.setBin("fixed", 2)

        # Scope label
        self._scope_label = OnscreenText(
            text="SCOPE", pos=(-0.42, -0.57), scale=0.03,
            fg=(0, 1, 0, 0.7), align=TextNode.ALeft,
            parent=self.aspect2d,
            mayChange=True,
        )
        self._scope_label.setBin("fixed", 2)

        # === Thermal imaging overlay ===
        self._scope_thermal = False

        # A second card in the same position, with a GLSL shader that
        # reads the scope texture and outputs a thermal colour palette.
        import os
        shader_dir = os.path.join(os.path.dirname(__file__), "rendering")
        thermal_shader = Shader.load(
            Shader.SL_GLSL,
            vertex=os.path.join(shader_dir, "thermal_vert.glsl"),
            fragment=os.path.join(shader_dir, "thermal.glsl"),
        )

        cm_th = CardMaker("scope_thermal")
        cm_th.setFrame(-0.45, -0.05, -0.95, -0.55)
        self.scope_thermal_card = self.aspect2d.attachNewNode(cm_th.generate())
        self.scope_thermal_card.setTexture(self.scope_texture)
        self.scope_thermal_card.setShader(thermal_shader)
        self.scope_thermal_card.setBin("fixed", 1)
        self.scope_thermal_card.hide()

    def _toggle_scope_thermal(self):
        """Toggle thermal imaging mode on the scope PIP."""
        self._scope_thermal = not self._scope_thermal
        if self._scope_thermal:
            self.scope_card.hide()
            self.scope_thermal_card.show()
            self._scope_label.setText("THERMAL")
            self._scope_label.setFg((1, 0.4, 0.1, 0.9))
            self._scope_crosshair.setFg((1, 1, 0.8, 0.9))
        else:
            self.scope_thermal_card.hide()
            self.scope_card.show()
            self._scope_label.setText("SCOPE")
            self._scope_label.setFg((0, 1, 0, 0.7))
            self._scope_crosshair.setFg((0, 1, 0, 0.8))

    def _update_scope_camera(self):
        """Scope camera is parented to turret pitch_np — no manual update needed.

        It automatically inherits yaw (from yaw_np) and elevation (from pitch_np)
        transforms set in _update_turret_visual.
        """
        pass

    # =========================================================
    # DEBUG PANEL & VISUALIZATIONS
    # =========================================================

    def _setup_scope_debug(self):
        """Create DevTools panel — permanent right sidebar with telemetry and debug toggles."""
        from direct.gui.DirectGui import DirectButton, DirectFrame, DGG

        # --- Debug state flags ---
        self.debug_flags = {
            "scope_frustum": False,
            "scope_axes": False,
            "wireframe": False,
            "bullet_trails": False,
            "show_fps": True,
            "scope_pip": True,
            "night_mode": self._is_night,
        }

        # --- 3D debug nodes ---
        self._scope_debug_np = self.render.attachNewNode("scope_debug")

        # --- Palette ---
        BG          = (0.10, 0.10, 0.10, 0.97)
        SECTION_BG  = (0.14, 0.14, 0.14, 1)
        BTN_OFF     = (0.20, 0.20, 0.20, 1)
        BTN_ON      = (0.14, 0.50, 0.24, 1)
        TEXT_DIM    = (0.55, 0.55, 0.55, 1)
        TEXT_BRIGHT = (0.95, 0.95, 0.95, 1)
        ACCENT      = (1, 0.75, 0, 1)        # orange
        VAL_COLOR   = (0.75, 0.90, 1.0, 1)   # light blue for values
        HEAT_LO     = (0.3, 1, 0.4, 1)
        HEAT_HI     = (1, 0.3, 0.2, 1)
        SEPARATOR   = (0.25, 0.25, 0.25, 1)

        # --- Panel geometry (aspect2d coordinates) ---
        # aspect2d x range is roughly -AR .. +AR where AR = 16/9 ≈ 1.777
        AR = self.getAspectRatio()
        pw = 0.58                            # panel width in aspect2d units
        panel_x = AR - pw                    # left edge of panel
        ph = 2.0                             # full height (top 1.0 to bottom -1.0)

        self._devtools_pw = pw
        self._devtools_panel_x = panel_x

        # --- Main frame ---
        self._debug_panel = DirectFrame(
            frameColor=BG,
            frameSize=(0, pw, -ph, 0),
            pos=(panel_x, 0, 1.0),
            parent=self.aspect2d,
            sortOrder=100,
        )

        # ── Header ──────────────────────────────────────────────
        OnscreenText(
            text="DEVTOOLS", pos=(pw / 2, -0.035), scale=0.04,
            fg=ACCENT, align=TextNode.ACenter,
            parent=self._debug_panel,
        )
        # thin separator
        sep0 = DirectFrame(
            frameColor=SEPARATOR,
            frameSize=(0, pw, -0.002, 0),
            pos=(0, 0, -0.065),
            parent=self._debug_panel,
        )

        # ── Helper: section header ──────────────────────────────
        def section_header(title, y):
            OnscreenText(
                text=title, pos=(0.04, y + 0.005), scale=0.028,
                fg=ACCENT, align=TextNode.ALeft,
                parent=self._debug_panel,
            )
            return y - 0.04

        # ── Helper: data row (label + value) ────────────────────
        self._dt_labels = {}  # keyed name → OnscreenText (for live updates)

        def data_row(name, label_text, y, val_text="—"):
            OnscreenText(
                text=label_text, pos=(0.04, y), scale=0.026,
                fg=TEXT_DIM, align=TextNode.ALeft,
                parent=self._debug_panel,
            )
            vt = OnscreenText(
                text=val_text, pos=(pw - 0.04, y), scale=0.026,
                fg=VAL_COLOR, align=TextNode.ARight,
                parent=self._debug_panel,
                mayChange=True,
            )
            self._dt_labels[name] = vt
            return y - 0.035

        # ══════════════════════════════════════════════════════════
        # SECTION A — TURRET STATUS
        # ══════════════════════════════════════════════════════════
        y = -0.08
        y = section_header("TURRET", y)
        y = data_row("t_state",    "State",       y)
        y = data_row("t_azimuth",  "Azimuth",     y)
        y = data_row("t_elev",     "Elevation",   y)
        y = data_row("t_ammo",     "Ammo",        y)
        y = data_row("t_heat",     "Heat",        y)
        y = data_row("t_fired",    "Rounds fired", y)
        y = data_row("t_belts",    "Belts used",  y)

        # separator
        y -= 0.01
        DirectFrame(frameColor=SEPARATOR,
                    frameSize=(0, pw, -0.002, 0),
                    pos=(0, 0, y), parent=self._debug_panel)
        y -= 0.015

        # ══════════════════════════════════════════════════════════
        # SECTION B — TARGET INFO
        # ══════════════════════════════════════════════════════════
        y = section_header("TARGET", y)
        y = data_row("tgt_type",   "Type",      y)
        y = data_row("tgt_speed",  "Speed",     y)
        y = data_row("tgt_range",  "Range",     y)
        y = data_row("tgt_bear",   "Bearing",   y)
        y = data_row("tgt_elev",   "Elevation", y)
        y = data_row("tgt_status", "Status",    y)

        y -= 0.01
        DirectFrame(frameColor=SEPARATOR,
                    frameSize=(0, pw, -0.002, 0),
                    pos=(0, 0, y), parent=self._debug_panel)
        y -= 0.015

        # ══════════════════════════════════════════════════════════
        # SECTION C — WEATHER
        # ══════════════════════════════════════════════════════════
        y = section_header("WEATHER", y)
        y = data_row("w_temp",   "Temp",       y)
        y = data_row("w_press",  "Pressure",   y)
        y = data_row("w_humid",  "Humidity",   y)
        y = data_row("w_wind",   "Wind",       y)

        y -= 0.01
        DirectFrame(frameColor=SEPARATOR,
                    frameSize=(0, pw, -0.002, 0),
                    pos=(0, 0, y), parent=self._debug_panel)
        y -= 0.015

        # ══════════════════════════════════════════════════════════
        # SECTION D — DEBUG TOGGLES
        # ══════════════════════════════════════════════════════════
        y = section_header("DEBUG", y)

        self._debug_btns = {}
        toggle_items = [
            ("night_mode",    "Night Mode"),
            ("scope_frustum", "Scope Frustum"),
            ("scope_axes",    "Scope Axes"),
            ("wireframe",     "Wireframe"),
            ("bullet_trails", "Bullet Trails"),
            ("show_fps",      "FPS Meter"),
            ("scope_pip",     "Scope PIP"),
        ]

        for key, label in toggle_items:
            is_on = self.debug_flags[key]
            btn = DirectButton(
                text=f"  {label}",
                text_align=TextNode.ALeft,
                text_fg=TEXT_BRIGHT if is_on else TEXT_DIM,
                text_scale=0.028,
                pos=(0.04, 0, y),
                frameSize=(0, pw - 0.16, -0.018, 0.018),
                frameColor=BTN_ON if is_on else BTN_OFF,
                relief=DGG.FLAT,
                command=self._on_debug_btn,
                extraArgs=[key],
                parent=self._debug_panel,
            )
            self._debug_btns[key] = btn

            indicator = OnscreenText(
                text="ON" if is_on else "OFF",
                pos=(pw - 0.06, y + 0.003), scale=0.024,
                fg=HEAT_LO if is_on else TEXT_DIM,
                align=TextNode.ACenter,
                parent=self._debug_panel,
                mayChange=True,
            )
            btn.setPythonTag("indicator", indicator)
            y -= 0.045

        y -= 0.01
        DirectFrame(frameColor=SEPARATOR,
                    frameSize=(0, pw, -0.002, 0),
                    pos=(0, 0, y), parent=self._debug_panel)
        y -= 0.015

        # ══════════════════════════════════════════════════════════
        # SECTION E — PERFORMANCE
        # ══════════════════════════════════════════════════════════
        y = section_header("PERFORMANCE", y)
        y = data_row("p_fps",     "FPS",           y)
        y = data_row("p_projs",   "Projectiles",   y)

        # ── Footer ──────────────────────────────────────────────
        OnscreenText(
            text="]  toggle  |  V  thermal  |  C  camera  |  N  night",
            pos=(pw / 2, -ph + 0.02), scale=0.022,
            fg=(0.35, 0.35, 0.35, 1), align=TextNode.ACenter,
            parent=self._debug_panel,
        )

        # ── Viewport resize ─────────────────────────────────────
        # Shrink main 3D viewport to make room for the panel
        self._debug_panel_visible = True
        self._debug_panel.show()
        self._set_viewport_for_panel(True)

        # Hide right-side HUD texts (now shown in panel)
        for key in ("turret_state", "ammo", "heat", "orientation",
                    "weather", "wind", "target_info", "target_dist", "target_alt"):
            if key in self.hud_texts:
                self.hud_texts[key].hide()

        # ] key
        self.accept("]", self._toggle_debug_panel)

    def _set_viewport_for_panel(self, panel_open):
        """Resize the main camera display region based on panel visibility."""
        # The main camera DR is typically at index 0, but let's find it
        # by looking for the one driven by self.cam.
        if panel_open:
            # Leave right 25% for panel — map aspect2d panel_x to viewport fraction
            vp_right = 1.0 - (self._devtools_pw / (2 * self.getAspectRatio()))
            # Clamp to something reasonable
            vp_right = max(0.6, min(0.85, vp_right))
        else:
            vp_right = 1.0

        # Resize all main window display regions (excluding overlay at idx 0)
        for i in range(self.win.getNumDisplayRegions()):
            dr = self.win.getDisplayRegion(i)
            cam = dr.getCamera()
            if cam and cam == self.cam:
                dr.setDimensions(0, vp_right, 0, 1)
                break

    def _toggle_debug_panel(self):
        self._debug_panel_visible = not self._debug_panel_visible
        if self._debug_panel_visible:
            self._debug_panel.show()
            self._set_viewport_for_panel(True)
            # Hide right-side HUD texts (info is in panel)
            for key in ("turret_state", "ammo", "heat", "orientation",
                        "weather", "wind", "target_info", "target_dist", "target_alt"):
                if key in self.hud_texts:
                    self.hud_texts[key].hide()
        else:
            self._debug_panel.hide()
            self._set_viewport_for_panel(False)
            # Restore right-side HUD texts
            for key in ("turret_state", "ammo", "heat", "orientation",
                        "weather", "wind", "target_info", "target_dist", "target_alt"):
                if key in self.hud_texts:
                    self.hud_texts[key].show()

    def _update_devtools(self):
        """Update live data in the DevTools panel every frame."""
        if not self._debug_panel_visible:
            return

        gm = self.game_mgr
        turret = gm.turret
        dt = self._dt_labels

        # Turret status
        state_colors = {
            "ready":         (0.3, 1, 0.4, 1),
            "firing":        (1, 0.8, 0.2, 1),
            "reloading":     (0.4, 0.7, 1, 1),
            "overheated":    (1, 0.3, 0.2, 1),
            "barrel_change": (0.8, 0.5, 1, 1),
        }
        state_val = turret.state.value
        dt["t_state"].setText(state_val.upper())
        dt["t_state"].setFg(state_colors.get(state_val, (0.8, 0.8, 0.8, 1)))

        dt["t_azimuth"].setText(f"{np.degrees(turret.azimuth):.1f}\u00b0")
        dt["t_elev"].setText(f"{np.degrees(turret.elevation):.1f}\u00b0")
        dt["t_ammo"].setText(f"{turret.ammo_remaining} / {turret.config.belt_capacity}")
        heat_pct = turret.heat_level / turret.config.overheat_threshold * 100
        dt["t_heat"].setText(f"{heat_pct:.0f}%")
        # Color gradient for heat: green → red
        ht = min(1.0, heat_pct / 100)
        dt["t_heat"].setFg((ht, 1 - ht * 0.7, 0.2, 1))
        dt["t_fired"].setText(str(turret.total_rounds_fired))
        dt["t_belts"].setText(str(turret.belts_used))

        # Target info
        if gm.current_target and gm.current_target.alive:
            tgt = gm.current_target
            bearing_rad, elev_rad = tgt.get_bearing_elevation()
            dt["tgt_type"].setText(tgt.profile.name)
            dt["tgt_speed"].setText(f"{tgt.speed:.0f} m/s")
            dt["tgt_range"].setText(f"{tgt.range_from_origin:.0f} m")
            dt["tgt_bear"].setText(f"{np.degrees(bearing_rad):.1f}\u00b0")
            dt["tgt_elev"].setText(f"{np.degrees(elev_rad):.1f}\u00b0")
            dt["tgt_status"].setText("ALIVE")
            dt["tgt_status"].setFg((0.3, 1, 0.4, 1))
        else:
            for k in ("tgt_type", "tgt_speed", "tgt_range", "tgt_bear", "tgt_elev"):
                dt[k].setText("\u2014")
            if gm.current_target and not gm.current_target.alive:
                dt["tgt_status"].setText("DESTROYED")
                dt["tgt_status"].setFg((1, 0.3, 0.2, 1))
            else:
                dt["tgt_status"].setText("NONE")
                dt["tgt_status"].setFg((0.5, 0.5, 0.5, 1))

        # Weather
        w = gm.weather
        dt["w_temp"].setText(f"{w.temperature_c:.0f}\u00b0C")
        dt["w_press"].setText(f"{w.pressure_hpa:.0f} hPa")
        dt["w_humid"].setText(f"{w.humidity_pct:.0f}%")
        dt["w_wind"].setText(f"{w.wind_speed_mps:.1f} m/s @ {w.wind_direction_deg:.0f}\u00b0")

        # Performance
        fps = globalClock.getAverageFrameRate()
        dt["p_fps"].setText(f"{fps:.0f}")
        dt["p_fps"].setFg((0.3, 1, 0.4, 1) if fps >= 30 else (1, 0.3, 0.2, 1))
        n_proj = len(self.tracer_nodes) if hasattr(self, 'tracer_nodes') else 0
        dt["p_projs"].setText(str(n_proj))

    def _on_debug_btn(self, key):
        """Toggle a debug flag via button click."""
        # Night mode has its own toggle that updates the button
        if key == "night_mode":
            self._toggle_day_night()
            return

        self.debug_flags[key] = not self.debug_flags[key]
        is_on = self.debug_flags[key]

        BTN_OFF = (0.20, 0.20, 0.20, 1)
        BTN_ON = (0.14, 0.50, 0.24, 1)

        btn = self._debug_btns[key]
        btn["frameColor"] = BTN_ON if is_on else BTN_OFF
        btn["text_fg"] = (0.95, 0.95, 0.95, 1) if is_on else (0.55, 0.55, 0.55, 1)

        indicator = btn.getPythonTag("indicator")
        if indicator:
            indicator.setText("ON" if is_on else "OFF")
            indicator.setFg((0.3, 1, 0.4, 1) if is_on else (0.55, 0.55, 0.55, 1))

        self._apply_debug_flags()

    def _apply_debug_flags(self):
        """Apply debug flag changes that need immediate action."""
        if self.debug_flags["wireframe"]:
            self.render.setRenderModeWireframe()
        else:
            self.render.clearRenderMode()

        self.setFrameRateMeter(self.debug_flags["show_fps"])

        if self.debug_flags["scope_pip"]:
            if self._scope_thermal:
                self.scope_thermal_card.show()
            else:
                self.scope_card.show()
        else:
            self.scope_card.hide()
            self.scope_thermal_card.hide()

    def _update_scope_debug(self):
        """Redraw scope camera debug visuals each frame."""
        self._scope_debug_np.node().removeAllChildren()

        show_axes = self.debug_flags["scope_axes"]
        show_frustum = self.debug_flags["scope_frustum"]

        if not show_axes and not show_frustum:
            return

        cam_pos = self.scope_cam.getPos(self.render)
        cam_mat = self.scope_cam.getMat(self.render)

        # Local axes from the 4×4 matrix (rows 0,1,2 = right, fwd, up)
        right = LVector3(cam_mat.getRow3(0))
        fwd = LVector3(cam_mat.getRow3(1))
        up = LVector3(cam_mat.getRow3(2))

        ls = LineSegs("scope_debug_lines")

        if show_axes:
            axis_len = 1.0
            ls.setThickness(3)
            # X — red
            ls.setColor(1, 0, 0, 1)
            ls.moveTo(cam_pos)
            ls.drawTo(cam_pos + right * axis_len)
            # Y — green
            ls.setColor(0, 1, 0, 1)
            ls.moveTo(cam_pos)
            ls.drawTo(cam_pos + fwd * axis_len)
            # Z — blue
            ls.setColor(0, 0.4, 1, 1)
            ls.moveTo(cam_pos)
            ls.drawTo(cam_pos + up * axis_len)

        if show_frustum:
            lens = self.scope_cam.node().getLens()
            fov_h = math.radians(lens.getFov()[0] / 2)
            fov_v = math.radians(lens.getFov()[1] / 2)
            frustum_len = 10.0

            corners = [
                fwd * frustum_len + right * (frustum_len * math.tan(fov_h)) + up * (frustum_len * math.tan(fov_v)),
                fwd * frustum_len - right * (frustum_len * math.tan(fov_h)) + up * (frustum_len * math.tan(fov_v)),
                fwd * frustum_len - right * (frustum_len * math.tan(fov_h)) - up * (frustum_len * math.tan(fov_v)),
                fwd * frustum_len + right * (frustum_len * math.tan(fov_h)) - up * (frustum_len * math.tan(fov_v)),
            ]

            ls.setColor(1, 1, 0, 0.6)
            ls.setThickness(1.5)
            for c in corners:
                ls.moveTo(cam_pos)
                ls.drawTo(cam_pos + c)
            for i in range(4):
                ls.moveTo(cam_pos + corners[i])
                ls.drawTo(cam_pos + corners[(i + 1) % 4])

        node = ls.create()
        self._scope_debug_np.attachNewNode(node)

    # =========================================================
    # INPUT CONTROLS
    # =========================================================

    def _setup_controls(self):
        """Set up keyboard and mouse input."""
        # Key states
        # Movement and firing are polled directly via isButtonDown in
        # _handle_keyboard — no event bindings needed for arrows/WASD/space.

        self.accept("r", self._on_reload)
        self.accept("enter", self._on_enter)
        self.accept("t", self._on_training)
        self.accept("c", self._toggle_camera_mode)
        self.accept("v", self._toggle_scope_thermal)
        self.accept("n", self._toggle_day_night)
        self.accept("escape", sys.exit)

        # Mouse - orbit camera (LMB or MMB)
        self.accept("mouse1", self._on_mouse_down)
        self.accept("mouse1-up", self._on_mouse_up)
        self.accept("mouse2", self._on_mouse_down)
        self.accept("mouse2-up", self._on_mouse_up)
        self.accept("wheel_up", self._on_scroll, [-1])
        self.accept("wheel_down", self._on_scroll, [1])

    def _on_reload(self):
        self.game_mgr.turret.reload()

    def _on_enter(self):
        if self.game_mgr.state == GameState.MENU:
            self.game_mgr.start_game()
            # Re-bind API server to new turret/engine instances
            self.api_server.bind(
                turret=self.game_mgr.turret,
                target_manager=self.game_mgr.target_manager,
                game_manager=self.game_mgr,
                ballistics_engine=self.game_mgr.engine,
            )
        elif self.game_mgr.state in (GameState.ROUND_END, GameState.TARGET_HIT,
                                      GameState.TARGET_ESCAPED):
            self.game_mgr.next_round()

    def _on_training(self):
        """Start training mode with static target."""
        if self.game_mgr.state == GameState.MENU:
            self.game_mgr.start_training()
            self.api_server.bind(
                turret=self.game_mgr.turret,
                target_manager=self.game_mgr.target_manager,
                game_manager=self.game_mgr,
                ballistics_engine=self.game_mgr.engine,
            )

    def _on_mouse_down(self):
        if self.cam_mode == "first_person":
            return  # Mouse drag not used in FP mode
        self._mouse_dragging = True
        if self.mouseWatcherNode.hasMouse():
            self._last_mouse_x = self.mouseWatcherNode.getMouseX()
            self._last_mouse_y = self.mouseWatcherNode.getMouseY()

    def _on_mouse_up(self):
        self._mouse_dragging = False

    def _on_scroll(self, direction):
        if self.cam_mode == "first_person":
            return  # Scroll not used in FP mode
        self.cam_distance = max(3, min(50, self.cam_distance + direction * 1.5))
        self._update_camera()

    def _handle_mouse(self):
        """Handle mouse input — orbit in orbit mode, turret aim in first-person."""
        if self.cam_mode == "first_person":
            self._handle_mouse_fp()
            return

        if not self._mouse_dragging or not self.mouseWatcherNode.hasMouse():
            return

        mx = self.mouseWatcherNode.getMouseX()
        my = self.mouseWatcherNode.getMouseY()
        dx = mx - self._last_mouse_x
        dy = my - self._last_mouse_y
        self._last_mouse_x = mx
        self._last_mouse_y = my

        self.cam_heading -= dx * 200
        self.cam_pitch = max(-85, min(85, self.cam_pitch - dy * 100))
        self._update_camera()

    def _handle_mouse_fp(self):
        """First-person mouse aim: mouse offset from center controls turret."""
        if not self.mouseWatcherNode.hasMouse():
            return

        mx = self.mouseWatcherNode.getMouseX()
        my = self.mouseWatcherNode.getMouseY()

        # Sensitivity: degrees per unit of mouse offset
        sensitivity = 1.5

        turret = self.game_mgr.turret
        target_az = turret.target_azimuth + mx * np.radians(sensitivity)
        target_el = turret.target_elevation + my * np.radians(sensitivity)
        turret.set_target(target_az, target_el)

        # Re-center the mouse to create continuous aiming
        props = self.win.getProperties()
        cx = props.getXSize() // 2
        cy = props.getYSize() // 2
        self.win.movePointer(0, cx, cy)

    def _handle_keyboard(self, dt):
        """Handle manual turret control — aiming always works, firing only when PLAYING.

        Uses direct button polling (isButtonDown) instead of event-based key_map
        so that simultaneous X+Y axis input is always detected reliably.
        """
        turret = self.game_mgr.turret
        manual_speed_rad = np.radians(30.0)  # 30 deg/s in radians

        # Poll keyboard state directly — guaranteed to read all held keys
        is_down = self.mouseWatcherNode.isButtonDown

        move_left = is_down(KeyboardButton.left()) or is_down(KeyboardButton.asciiKey("a"))
        move_right = is_down(KeyboardButton.right()) or is_down(KeyboardButton.asciiKey("d"))
        move_up = is_down(KeyboardButton.up()) or is_down(KeyboardButton.asciiKey("w"))
        move_down = is_down(KeyboardButton.down()) or is_down(KeyboardButton.asciiKey("s"))
        firing = is_down(KeyboardButton.space())

        target_az = turret.target_azimuth
        target_el = turret.target_elevation

        if move_left:
            target_az -= manual_speed_rad * dt
        if move_right:
            target_az += manual_speed_rad * dt
        if move_up:
            target_el += manual_speed_rad * dt * 0.7
        if move_down:
            target_el -= manual_speed_rad * dt * 0.7

        turret.set_target(target_az, target_el)

        # Only allow firing during active gameplay or training
        can_fire = self.game_mgr.state in (GameState.PLAYING, GameState.TRAINING)
        if can_fire and firing:
            turret.start_firing()
        else:
            turret.stop_firing()

    # =========================================================
    # VISUAL UPDATES
    # =========================================================

    def _update_turret_visual(self):
        """Update turret 3D model to match game state."""
        turret = self.game_mgr.turret

        # Yaw (Panda3D H = heading, rotates around Z)
        # Our azimuth: 0=North(+Y), positive=clockwise
        # Panda3D H: 0=+Y, positive=counterclockwise
        self.turret_parts["yaw"].setH(-np.degrees(turret.azimuth))

        # Pitch (elevation)
        # Panda3D P: positive = nose up; barrel cylinders already have setP(-90)
        # to lay along +Y, so positive P on parent pitches barrels upward.
        self.turret_parts["pitch"].setP(np.degrees(turret.elevation))

    def _update_target_visual(self):
        """Update or create target 3D model."""
        target = self.game_mgr.current_target

        if target and target.alive:
            if self.target_np is None:
                if self.game_mgr.training_mode:
                    # Training: light aircraft model at altitude
                    self.target_np = build_training_target(self.render)
                    pos = target.position
                    self.target_np.setPos(pos[0], pos[1], pos[2])
                else:
                    # Normal: aerial target model
                    self.target_np = build_target_model(
                        self.render,
                        target.profile.target_type.value,
                        target.profile.hit_radius,
                    )
                    pos = target.position
                    self.target_np.setPos(pos[0], pos[1], pos[2])
            if not self.game_mgr.training_mode:
                # Update position for moving targets
                pos = target.position
                self.target_np.setPos(pos[0], pos[1], pos[2])
            self.target_np.show()
        else:
            if self.target_np:
                self.target_np.hide()

    def _update_tracers(self):
        """Update bullet tracer visuals using engine tracer trails."""
        # Remove old tracer nodes
        for node in self.tracer_nodes:
            node.removeNode()
        self.tracer_nodes.clear()

        trails = self.game_mgr.engine.get_tracer_trails()

        for trail in trails:
            if len(trail) < 2:
                continue

            segs = LineSegs("tracer")
            segs.setThickness(2.0)

            # Use last 30 points for visible trail
            visible = trail[-30:]
            for i, pos in enumerate(visible):
                t = i / len(visible)
                r = 1.0
                g = 0.9 * (1 - t * 0.7)
                b = 0.2 * (1 - t)
                a = 0.3 + 0.7 * t
                segs.setColor(r, g, b, a)
                # ENU maps directly to Panda3D (X, Y, Z)
                if i == 0:
                    segs.moveTo(pos[0], pos[1], pos[2])
                else:
                    segs.drawTo(pos[0], pos[1], pos[2])

            node = self.render.attachNewNode(segs.create())
            node.setLightOff()
            node.setBin("fixed", 5)
            node.setTransparency(TransparencyAttrib.MAlpha)
            self.tracer_nodes.append(node)

    def _update_muzzle_flash(self, dt):
        """Show muzzle flash when firing."""
        if self.muzzle_flash_timer > 0:
            self.muzzle_flash_timer -= dt
            # Random flash size
            s = random.uniform(0.8, 1.5)
            if self.next_barrel == 0:
                self.flash_l.show()
                self.flash_l.setScale(s)
                self.flash_r.hide()
            else:
                self.flash_r.show()
                self.flash_r.setScale(s)
                self.flash_l.hide()
        else:
            self.flash_l.hide()
            self.flash_r.hide()

    # =========================================================
    # GAME EVENTS
    # =========================================================

    def _on_game_event(self, event):
        """Handle game events."""
        etype = event.get("type")
        # Push to WebSocket
        self.ws_server.push_event(event)

        if etype == "shot_fired":
            self.muzzle_flash_timer = 0.03
            self.next_barrel = 1 - self.next_barrel

        elif etype in ("target_hit", "training_hit"):
            # Create explosion effect
            if self.target_np:
                self._create_explosion(self.target_np.getPos())
                # Remove target visual so it disappears; will be recreated on respawn
                self.target_np.removeNode()
                self.target_np = None

    def _create_explosion(self, pos):
        """Simple explosion effect (expanding sphere)."""
        explosion = make_sphere("explosion", 2.0, 8, 6, (1, 0.6, 0.1, 0.8))
        explosion.reparentTo(self.render)
        explosion.setPos(pos)
        explosion.setTransparency(TransparencyAttrib.MAlpha)
        explosion.setLightOff()
        explosion.setBin("fixed", 8)

        # Animate with task
        start_scale = 0.1
        explosion.setScale(start_scale)

        def expand_task(task):
            t = task.time
            if t > 1.0:
                explosion.removeNode()
                return Task.done
            scale = start_scale + t * 5
            alpha = max(0, 1 - t)
            explosion.setScale(scale)
            explosion.setColor(1, 0.6 - t*0.3, 0.1, alpha)
            return Task.cont

        self.taskMgr.add(expand_task, "explosion")

    # =========================================================
    # MAIN UPDATE LOOP
    # =========================================================

    def _update(self, task):
        """Main game loop - called every frame."""
        dt = globalClock.getDt()
        dt = min(dt, 0.05)  # Cap delta time

        # Input
        self._handle_mouse()
        self._handle_keyboard(dt)

        # Game logic
        events = self.game_mgr.update(dt)

        # Process events
        for event in events:
            self._on_game_event(event)

        # Re-bind API references after start_game (which recreates turret/engine)
        # This ensures API always points to current instances
        if any(e.get("type") == "game_started" for e in events):
            self.api_server.bind(
                turret=self.game_mgr.turret,
                target_manager=self.game_mgr.target_manager,
                game_manager=self.game_mgr,
                ballistics_engine=self.game_mgr.engine,
            )

        # Visuals
        self._update_turret_visual()
        self._update_target_visual()
        self._update_tracers()
        self._update_muzzle_flash(dt)
        self._update_scope_camera()
        self._update_scope_debug()
        self._update_hud()
        self._update_devtools()

        # Slow cloud drift (~0.3 deg/s rotation)
        if hasattr(self, 'cloud_root'):
            self.cloud_root.setH(self.cloud_root.getH() + dt * 0.3)

        return Task.cont


def main():
    """Entry point."""
    app = TurretSimApp()
    app.run()


if __name__ == "__main__":
    main()

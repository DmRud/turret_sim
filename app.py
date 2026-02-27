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
  T               : Training mode (static target at 200 m)
  F1              : Toggle debug panel
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
    AmbientLight, DirectionalLight, PointLight,
    TextNode, CardMaker,
    WindowProperties, FrameBufferProperties,
    GraphicsOutput, GraphicsPipe, Texture,
    DisplayRegion, Camera, Lens, PerspectiveLens,
    TransparencyAttrib, ColorBlendAttrib,
    AntialiasAttrib, RenderModeAttrib,
    KeyboardButton, BitMask32,
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
    build_training_target,
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
        print("    LMB / MMB drag    : Orbit camera")
        print("    Scroll            : Zoom camera")
        print("    F1                : Toggle debug panel")
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
        # Background color (sky)
        self.setBackgroundColor(0.55, 0.7, 0.9, 1)

        # Environment
        self.env_root = self.render.attachNewNode("environment")
        build_environment(self.env_root)

        # Enable antialiasing
        self.render.setAntialias(AntialiasAttrib.MAuto)

    def _setup_lights(self):
        """Set up scene lighting."""
        # Ambient
        alight = AmbientLight('ambient')
        alight.setColor(LVector4(0.3, 0.3, 0.35, 1))
        self.render.setLight(self.render.attachNewNode(alight))

        # Sun (directional)
        dlight = DirectionalLight('sun')
        dlight.setColor(LVector4(1.0, 0.95, 0.85, 1))
        dlnp = self.render.attachNewNode(dlight)
        dlnp.setHpr(45, -45, 0)
        self.render.setLight(dlnp)

        # Fill light
        dlight2 = DirectionalLight('fill')
        dlight2.setColor(LVector4(0.3, 0.35, 0.4, 1))
        dlnp2 = self.render.attachNewNode(dlight2)
        dlnp2.setHpr(-135, -30, 0)
        self.render.setLight(dlnp2)

    def _setup_camera(self):
        """Set up orbit camera."""
        self.disableMouse()

        self.cam_distance = 8.0
        self.cam_heading = 30.0
        self.cam_pitch = -25.0
        self.cam_target = LPoint3(0, 0, 1.2)

        self._update_camera()

        # Mouse state
        self._mouse_dragging = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0

    def _update_camera(self):
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

    def _setup_turret(self):
        """Build and set up turret model."""
        self.turret_root = self.render.attachNewNode("turret_root")
        self.turret_parts = build_turret_model(self.turret_root)

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

        # Bottom left - target info
        add_text("target_info", (-1.7, -0.75))
        add_text("target_dist", (-1.7, -0.82))

        # Bottom right - weather
        add_text("weather", (1.7, -0.75), TextNode.ARight)
        add_text("wind", (1.7, -0.82), TextNode.ARight)

        # Center - hit/miss notifications
        add_text("notification", (0, 0.2), TextNode.ACenter, 0.1)

        # Bottom center - stats
        add_text("stats", (0, -0.9), TextNode.ACenter, 0.04)

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

        # Turret — state, ammo, heat, orientation (convert radians to degrees)
        texts["turret_state"].setText(f"Turret: {turret.state.value.upper()}")
        texts["ammo"].setText(
            f"Ammo: {turret.ammo_remaining}/{turret.config.belt_capacity}")

        heat_pct = turret.heat_level / turret.config.overheat_threshold * 100
        heat_bar = "#" * int(heat_pct / 5) + "." * (20 - int(heat_pct / 5))
        texts["heat"].setText(f"Heat: [{heat_bar}] {heat_pct:.0f}%")

        az_deg = np.degrees(turret.azimuth)
        el_deg = np.degrees(turret.elevation)
        texts["orientation"].setText(
            f"Az: {az_deg:.1f}\u00b0 El: {el_deg:.1f}\u00b0")

        # Target info — use new Target API
        if gm.current_target and gm.current_target.alive:
            tgt = gm.current_target
            bearing_rad, elev_rad = tgt.get_bearing_elevation()
            texts["target_info"].setText(
                f"Target: {tgt.profile.name} | Speed: {tgt.speed:.0f} m/s")
            texts["target_dist"].setText(
                f"Distance: {tgt.range_from_origin:.0f}m | "
                f"Bearing: {np.degrees(bearing_rad):.1f}\u00b0 | "
                f"Elev: {np.degrees(elev_rad):.1f}\u00b0")
        else:
            texts["target_info"].setText("")
            texts["target_dist"].setText("")

        # Weather — use humidity_pct
        w = gm.weather
        texts["weather"].setText(
            f"Temp: {w.temperature_c:.0f}\u00b0C | "
            f"Press: {w.pressure_hpa:.0f}hPa | "
            f"Humid: {w.humidity_pct:.0f}%")
        texts["wind"].setText(
            f"Wind: {w.wind_speed_mps:.1f}m/s from {w.wind_direction_deg:.0f}\u00b0")

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
        self.scope_buffer.setClearColor(LColor(0.55, 0.7, 0.9, 1))

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
        )
        self._scope_label.setBin("fixed", 2)

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
        """Create debug visualizations and a toggle panel (F1)."""
        from direct.gui.DirectGui import DirectButton, DirectFrame, DGG

        # --- Debug state flags ---
        self.debug_flags = {
            "scope_frustum": False,
            "scope_axes": False,
            "wireframe": False,
            "bullet_trails": False,
            "show_fps": True,
            "scope_pip": True,
        }

        # --- 3D debug nodes ---
        self._scope_debug_np = self.render.attachNewNode("scope_debug")

        # --- Colors ---
        BG = (0.12, 0.12, 0.12, 0.92)
        BTN_OFF = (0.22, 0.22, 0.22, 1)
        BTN_ON = (0.15, 0.55, 0.25, 1)
        TEXT_DIM = (0.6, 0.6, 0.6, 1)
        TEXT_BRIGHT = (1, 1, 1, 1)

        # --- Panel frame ---
        pw, ph = 0.46, 0.82
        self._debug_panel = DirectFrame(
            frameColor=BG,
            frameSize=(0, pw, -ph, 0),
            pos=(1.22, 0, 0.92),
            parent=self.aspect2d,
            sortOrder=100,
        )

        # Title
        OnscreenText(
            text="DEBUG", pos=(pw / 2, -0.04), scale=0.042,
            fg=(1, 0.75, 0, 1), align=TextNode.ACenter,
            parent=self._debug_panel,
            font=None,
        )

        # --- Build toggle buttons ---
        self._debug_btns = {}

        sections = [
            ("Visualization", [
                ("scope_frustum", "Scope Frustum"),
                ("scope_axes",    "Scope Axes"),
                ("wireframe",     "Wireframe"),
                ("bullet_trails", "Bullet Trails"),
            ]),
            ("Display", [
                ("show_fps",  "FPS Meter"),
                ("scope_pip", "Scope PIP"),
            ]),
        ]

        y = -0.10
        for section_name, items in sections:
            # Section header
            OnscreenText(
                text=section_name, pos=(0.04, y), scale=0.03,
                fg=TEXT_DIM, align=TextNode.ALeft,
                parent=self._debug_panel,
            )
            y -= 0.05

            for key, label in items:
                is_on = self.debug_flags[key]
                btn = DirectButton(
                    text=f"  {label}",
                    text_align=TextNode.ALeft,
                    text_fg=TEXT_BRIGHT if is_on else TEXT_DIM,
                    text_scale=0.035,
                    pos=(0.04, 0, y),
                    frameSize=(0, pw - 0.08, -0.025, 0.025),
                    frameColor=BTN_ON if is_on else BTN_OFF,
                    relief=DGG.FLAT,
                    command=self._on_debug_btn,
                    extraArgs=[key],
                    parent=self._debug_panel,
                )
                self._debug_btns[key] = btn

                # Status indicator on the right
                indicator = OnscreenText(
                    text="ON" if is_on else "OFF",
                    pos=(pw - 0.12, y + 0.005), scale=0.028,
                    fg=(0.3, 1, 0.4, 1) if is_on else (0.5, 0.5, 0.5, 1),
                    align=TextNode.ALeft,
                    parent=self._debug_panel,
                    mayChange=True,
                )
                btn.setPythonTag("indicator", indicator)
                y -= 0.06

            y -= 0.02  # Gap between sections

        # Footer
        OnscreenText(
            text="F1 — toggle panel", pos=(pw / 2, y - 0.01), scale=0.025,
            fg=(0.4, 0.4, 0.4, 1), align=TextNode.ACenter,
            parent=self._debug_panel,
        )

        # Start hidden
        self._debug_panel.hide()
        self._debug_panel_visible = False

        # F1 key
        self.accept("f1", self._toggle_debug_panel)

    def _toggle_debug_panel(self):
        self._debug_panel_visible = not self._debug_panel_visible
        if self._debug_panel_visible:
            self._debug_panel.show()
        else:
            self._debug_panel.hide()

    def _on_debug_btn(self, key):
        """Toggle a debug flag via button click."""
        self.debug_flags[key] = not self.debug_flags[key]
        is_on = self.debug_flags[key]

        BTN_OFF = (0.22, 0.22, 0.22, 1)
        BTN_ON = (0.15, 0.55, 0.25, 1)

        btn = self._debug_btns[key]
        btn["frameColor"] = BTN_ON if is_on else BTN_OFF
        btn["text_fg"] = (1, 1, 1, 1) if is_on else (0.6, 0.6, 0.6, 1)

        indicator = btn.getPythonTag("indicator")
        if indicator:
            indicator.setText("ON" if is_on else "OFF")
            indicator.setFg((0.3, 1, 0.4, 1) if is_on else (0.5, 0.5, 0.5, 1))

        self._apply_debug_flags()

    def _apply_debug_flags(self):
        """Apply debug flag changes that need immediate action."""
        if self.debug_flags["wireframe"]:
            self.render.setRenderModeWireframe()
        else:
            self.render.clearRenderMode()

        self.setFrameRateMeter(self.debug_flags["show_fps"])

        if self.debug_flags["scope_pip"]:
            self.scope_card.show()
        else:
            self.scope_card.hide()

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
        self._mouse_dragging = True
        if self.mouseWatcherNode.hasMouse():
            self._last_mouse_x = self.mouseWatcherNode.getMouseX()
            self._last_mouse_y = self.mouseWatcherNode.getMouseY()

    def _on_mouse_up(self):
        self._mouse_dragging = False

    def _on_scroll(self, direction):
        self.cam_distance = max(3, min(50, self.cam_distance + direction * 1.5))
        self._update_camera()

    def _handle_mouse(self):
        """Handle mouse orbit."""
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

        return Task.cont


def main():
    """Entry point."""
    app = TurretSimApp()
    app.run()


if __name__ == "__main__":
    main()

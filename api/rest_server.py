"""
REST API Server for Turret Control

Runs in a separate thread alongside the Panda3D application.
Provides endpoints for external scripts to control the turret.

Endpoints:
  GET  /status          — Turret status (orientation, ammo, heat, state)
  GET  /target          — Target info from monocular (only if visible)
  POST /aim             — Set turret aim direction {azimuth_deg, elevation_deg}
  POST /fire/start      — Start continuous fire
  POST /fire/stop       — Stop firing
  POST /fire/single     — Fire a single burst (N rounds)
  POST /reload          — Initiate reload
  GET  /game            — Game status (round, score, weather)
  POST /game/start      — Start new game
  GET  /weather         — Current weather conditions
  GET  /ballistics      — Projectile parameters
"""

import json
import threading
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

logger = logging.getLogger("turret_api")


class TurretAPI:
    """REST API for turret control, runs in background thread."""
    
    def __init__(self, host="127.0.0.1", port=8420):
        self.host = host
        self.port = port
        self.app = Flask("turret_api")
        CORS(self.app)
        
        # References to game objects (set by main app)
        self.turret = None
        self.target_manager = None
        self.game_manager = None
        self.ballistics_engine = None
        
        # Suppress Flask request logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)
        
        self._setup_routes()
        self._thread = None
    
    def bind(self, turret, target_manager, game_manager, ballistics_engine):
        """Bind game objects to API."""
        self.turret = turret
        self.target_manager = target_manager
        self.game_manager = game_manager
        self.ballistics_engine = ballistics_engine
    
    def start(self):
        """Start API server in background thread."""
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="turret_api"
        )
        self._thread.start()
        logger.info(f"REST API started on http://{self.host}:{self.port}")
    
    def _run(self):
        self.app.run(
            host=self.host,
            port=self.port,
            threaded=True,
            use_reloader=False,
        )
    
    def _setup_routes(self):
        app = self.app
        
        @app.route("/status", methods=["GET"])
        def get_status():
            if not self.turret:
                return jsonify({"error": "not initialized"}), 503
            return jsonify(self.turret.get_status())
        
        @app.route("/target", methods=["GET"])
        def get_target():
            """Get target through monocular — only visible if in FOV."""
            if not self.turret or not self.target_manager:
                return jsonify({"error": "not initialized"}), 503
            
            view = self.target_manager.get_monocular_view(
                self.turret.azimuth,
                self.turret.elevation,
                fov_deg=10.0
            )
            return jsonify(view)
        
        @app.route("/target/radar", methods=["GET"])
        def get_target_radar():
            """Full target info (debug/radar mode — not for challenge)."""
            if not self.target_manager:
                return jsonify({"error": "not initialized"}), 503
            info = self.target_manager.get_target_info()
            if info is None:
                return jsonify({"target": None})
            return jsonify(info)
        
        @app.route("/aim", methods=["POST"])
        def set_aim():
            if not self.turret:
                return jsonify({"error": "not initialized"}), 503
            
            data = request.get_json(force=True)
            
            import numpy as np
            if "azimuth_deg" in data and "elevation_deg" in data:
                az = np.radians(float(data["azimuth_deg"]))
                el = np.radians(float(data["elevation_deg"]))
                self.turret.set_target(az, el)
                return jsonify({
                    "ok": True,
                    "target_azimuth_deg": data["azimuth_deg"],
                    "target_elevation_deg": data["elevation_deg"],
                })
            
            return jsonify({"error": "provide azimuth_deg and elevation_deg"}), 400
        
        @app.route("/fire/start", methods=["POST"])
        def fire_start():
            if not self.turret:
                return jsonify({"error": "not initialized"}), 503
            self.turret.start_firing()
            return jsonify({"ok": True, "firing": True})
        
        @app.route("/fire/stop", methods=["POST"])
        def fire_stop():
            if not self.turret:
                return jsonify({"error": "not initialized"}), 503
            self.turret.stop_firing()
            return jsonify({"ok": True, "firing": False})
        
        @app.route("/fire/burst", methods=["POST"])
        def fire_burst():
            """Fire a burst of N rounds then stop."""
            if not self.turret:
                return jsonify({"error": "not initialized"}), 503
            
            data = request.get_json(force=True) if request.data else {}
            count = int(data.get("count", 5))
            
            # Start firing, will auto-stop after count
            self.turret.start_firing()
            # Note: burst control is approximate — actual stop happens in game loop
            return jsonify({"ok": True, "burst": count})
        
        @app.route("/reload", methods=["POST"])
        def reload():
            if not self.turret:
                return jsonify({"error": "not initialized"}), 503
            self.turret.reload()
            return jsonify({"ok": True, "state": "reloading"})
        
        @app.route("/game", methods=["GET"])
        def get_game():
            if not self.game_manager:
                return jsonify({"error": "not initialized"}), 503
            return jsonify(self.game_manager.get_full_status())
        
        @app.route("/game/start", methods=["POST"])
        def start_game():
            if not self.game_manager:
                return jsonify({"error": "not initialized"}), 503
            self.game_manager.start_game()
            return jsonify({"ok": True, "phase": "round_intro"})

        @app.route("/game/next", methods=["POST"])
        def next_round():
            if not self.game_manager:
                return jsonify({"error": "not initialized"}), 503
            self.game_manager.next_round()
            return jsonify({"ok": True, "round": self.game_manager.round_number})

        @app.route("/weather", methods=["GET"])
        def get_weather():
            if not self.game_manager:
                return jsonify({"error": "not initialized"}), 503
            w = self.game_manager.weather
            return jsonify({
                "temperature_c": round(w.temperature_c, 1),
                "pressure_hpa": round(w.pressure_hpa, 1),
                "humidity_pct": round(w.humidity_pct, 1),
                "wind_speed_mps": round(w.wind_speed_mps, 1),
                "wind_direction_deg": round(w.wind_direction_deg, 1),
                "altitude_m": round(w.altitude_m, 1),
            })
        
        @app.route("/ballistics", methods=["GET"])
        def get_ballistics():
            """Get projectile and atmospheric parameters."""
            from ballistics.tables import PROJECTILE_50BMG
            
            proj = {k: v for k, v in PROJECTILE_50BMG.items()
                    if not isinstance(v, type(lambda: 0))}
            # Convert numpy types
            for k, v in proj.items():
                if hasattr(v, 'item'):
                    proj[k] = v.item()
            
            atmo = {}
            if self.ballistics_engine:
                atmo = {
                    "air_density": round(self.ballistics_engine.atmosphere.air_density, 4),
                    "speed_of_sound": round(self.ballistics_engine.atmosphere.speed_of_sound, 1),
                    "density_ratio": round(self.ballistics_engine.atmosphere.density_ratio, 4),
                }
            
            return jsonify({
                "projectile": proj,
                "atmosphere": atmo,
            })
        
        @app.route("/", methods=["GET"])
        def index():
            return jsonify({
                "name": "Turret Simulator API",
                "version": "1.0",
                "endpoints": [
                    "GET  /status",
                    "GET  /target",
                    "GET  /target/radar",
                    "POST /aim {azimuth_deg, elevation_deg}",
                    "POST /fire/start",
                    "POST /fire/stop",
                    "POST /fire/burst {count}",
                    "POST /reload",
                    "GET  /game",
                    "POST /game/start",
                    "POST /game/next",
                    "GET  /weather",
                    "GET  /ballistics",
                ],
            })

# Turret Simulator — Browning M2 .50 Cal Twin Mount

A physics-accurate turret simulator with REST API control, real-time 3D visualization, and realistic .50 BMG ballistic modeling.

## Quick Start

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```bash
pip install -r requirements.txt
python main.py
```

The simulator starts with:
- **3D window** (Panda3D) — turret, targets, tracers, effects  
- **REST API** on `http://localhost:8420` (Swagger docs at `/docs`)  
- **WebSocket** events on `ws://localhost:8421`

Press **ENTER** in the 3D window to start.

---

## Controls (Manual Mode)

| Key | Action |
|-----|--------|
| Arrow keys / WASD | Rotate turret (simultaneous X+Y) |
| Space | Fire (hold) |
| R | Reload |
| Enter | Start game / Next round |
| T | Training mode (static target at 700 m) |
| C | Toggle first-person / orbit camera |
| V | Toggle scope thermal imaging |
| ] | Toggle debug panel |
| LMB / MMB drag | Orbit camera |
| Scroll | Zoom camera |
| ESC | Quit |

---

## REST API

Base URL: `http://localhost:8420`

### Endpoints

#### `GET /status`
Complete game status including turret, target, weather, monocular, stats.

#### `GET /turret/status`
```json
{
  "azimuth_deg": 45.2,
  "elevation_deg": 30.0,
  "state": "idle",
  "is_firing": false,
  "ammo_remaining": 180,
  "heat_percent": 12.5,
  "is_on_target": true,
  "dispersion_moa": 2.1
}
```

#### `POST /turret/rotate`
```json
{ "azimuth_deg": 45.0, "elevation_deg": 30.0 }
```
- Azimuth: -180° to 180° (0° = North, positive = clockwise)
- Elevation: 10° to 85°

#### `POST /turret/fire`
```json
{ "firing": true }
```

#### `POST /turret/reload`
Manual reload (8 second reload time).

#### `GET /monocular`
Scope view — returns target visibility only when target is within scope FOV (~5°).
```json
{
  "target_visible": true,
  "angular_offset_az": 1.2,
  "angular_offset_el": -0.5,
  "distance_m": 850.3,
  "angular_size_deg": 0.135
}
```

#### `GET /weather`
```json
{
  "temperature_c": 22.0,
  "pressure_hpa": 1013.0,
  "humidity_percent": 65.0,
  "wind_speed_mps": 5.2,
  "wind_direction_deg": 270.0
}
```

#### `POST /game/start` / `POST /game/next`
Game flow control.

---

## WebSocket Events

Connect to `ws://localhost:8421` for real-time events:

```json
{"type": "shot_fired", "time": 12.5, "azimuth": 45.2, "elevation": 30.0, "ammo_remaining": 179}
{"type": "target_hit", "round": 3, "time": 8.2, "rounds_fired": 25}
{"type": "target_escaped", "round": 3}
{"type": "overheated", "time": 15.3}
{"type": "cooled_down", "time": 25.3}
{"type": "reloaded", "ammo": 200}
{"type": "round_start", "round": 4, "description": "Faster medium drone"}
```

---

## Python Client SDK

```python
from client.turret_client import TurretClient

client = TurretClient()
client.start_game()

# Wait for round to start
import time; time.sleep(4)

# Get target info through scope
scope = client.get_monocular()
if scope["target_visible"]:
    print(f"Target at {scope['distance_m']}m")

# Aim and fire
client.rotate(azimuth=45.0, elevation=30.0)
client.wait_on_target()
client.burst(duration=1.0)

# Listen for events
client.on_event(lambda e: print(e))
```

### Example Scripts
- `client/example_simple_track.py` — Direct tracking (no lead)
- `client/example_lead_prediction.py` — Predictive aiming with TOF estimation

---

## Ballistic Model

Full point-mass ballistic simulation for .50 BMG M33 Ball.

### Projectile Specifications
| Parameter | Value |
|-----------|-------|
| Caliber | 12.7×99mm NATO |
| Bullet mass | 42.8 g (660 gr) |
| Muzzle velocity | 890 m/s |
| BC (G7) | 0.337 |
| BC (G1) | 0.670 |
| Barrel twist | 1:15" RH |

### Physics Modeled

1. **Aerodynamic Drag** — G7 drag model with Mach-dependent Cd from BRL tables, interpolated. Applied using ballistic coefficient method with form factor correction.

2. **Gravity** — Standard 9.80665 m/s², constant over trajectory.

3. **Atmospheric Model** — ICAO Standard Atmosphere:
   - Temperature with lapse rate (−6.5°C/km)
   - Barometric pressure variation with altitude
   - Humidity effects on air density (virtual temperature)
   - Speed of sound variation (Mach calculation)
   - Dynamic viscosity (Sutherland's law)

4. **Wind** — Constant wind vector per round, applied as modification to aerodynamic velocity (bullet velocity relative to air mass).

5. **Coriolis Effect** — Earth rotation acceleration: `a = −2(Ω × v)`. Configurable latitude (default 45°N).

6. **Magnus Effect (Spin Drift)** — Lateral force from bullet spin interacting with crossflow. Right-hand twist → rightward drift. Empirically calibrated to match known .50 BMG spin drift data (~0.5m at 1000m).

7. **Mechanical Dispersion** — Gaussian random angular offset, 2 MOA base (M2 spec), increases with barrel heat.

### Numerical Integration
4th-order Runge-Kutta (RK4) with 1ms timestep for trajectory computation, substeps for real-time updates.

---

## Turret Mechanics

### Browning M2HB Twin Mount
| Parameter | Value |
|-----------|-------|
| Rate of fire | 1000 rpm combined (500/barrel) |
| Belt capacity | 200 rounds |
| Reload time | 8 seconds |
| Azimuth range | Full 360° |
| Elevation range | 10° – 85° |
| Traverse speed | 60°/s |
| Elevation speed | 40°/s |

### Thermal Model
- Heat accumulation per shot: 1 unit
- Overheat threshold: 100 units
- Passive cooling: 5 units/s
- Forced cooldown: until 50% heat
- Heat increases dispersion

### Servo Model
- Acceleration-based rotation (not instant)
- Azimuth acceleration: 120°/s²
- Elevation acceleration: 80°/s²
- Smooth deceleration approaching target angle

---

## Architecture

```
turret_sim/
├── main.py                     # Entry point
├── app.py                      # Panda3D application (rendering + game loop)
├── ballistics/
│   ├── engine.py               # RK4 solver, all forces, optimized hot path
│   ├── atmosphere.py           # ICAO atmosphere + weather + density LUT
│   └── tables.py               # G1/G7 Cd(Mach) tables + dense O(1) lookup
├── turret/
│   └── model.py                # M2HB mechanics, thermal, servo model
├── targets/
│   └── manager.py              # Aerial target spawning + profiles
├── game/
│   └── manager.py              # Rounds, scoring, game state, training mode
├── api/
│   ├── rest_server.py          # REST API (Flask)
│   └── ws_server.py            # WebSocket event broadcaster
├── rendering/
│   └── models.py               # Procedural 3D geometry (turret, targets, env)
└── client/
    ├── turret_client.py         # Python SDK
    ├── example_simple_track.py
    └── example_lead_prediction.py
```

---

## Target Types

| Type | Speed | Altitude | Size | Description |
|------|-------|----------|------|-------------|
| Drone | 20–60 m/s | 100–500 m | 2.0 m | Small UAV |
| Light Aircraft | 50–120 m/s | 200–500 m | 8.0 m | Single-engine Cessna-style |
| Helicopter | 30–80 m/s | 100–400 m | 6.0 m | Rotary-wing |
| Cruise Missile | 200–300 m/s | 50–200 m | 4.0 m | Fast, low-altitude |

> **Note:** Current game rounds use Light Aircraft only. Other types are available via API.

---

## License

MIT — Educational / simulation purposes only.

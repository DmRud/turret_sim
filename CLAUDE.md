# Turret Simulator — Project Context for Claude Code

## PROJECT OVERVIEW
Realistic ballistics turret simulator: Browning M2HB (.50 BMG) dual-mounted on M3 tripod engaging aerial targets. Desktop application with Python + Panda3D.

## ARCHITECTURE

### Core Modules (IMPLEMENTED — need review/cleanup)
- `ballistics/tables.py` — G1/G7 drag coefficient tables, .50 BMG M33 projectile data
- `ballistics/atmosphere.py` — ICAO atmosphere model (temperature, pressure, humidity → air density, speed of sound)
- `ballistics/engine.py` — Full ballistic simulation: RK4 integrator, gravity, G7 drag, Magnus effect, Coriolis effect, wind
- `turret/model.py` — M2HB mechanical model: traverse/elevation rates, heat, ammo, reload, twin barrel alternation
- `targets/manager.py` — Aerial target spawning (drone, aircraft, helicopter, cruise missile), straight-line trajectories
- `game/round_manager.py` — Round-based gameplay: weather generation, scoring, statistics
- `api/rest_server.py` — Flask REST API for external script control (runs in thread)
- `api/ws_server.py` — WebSocket event broadcaster for push notifications

### NOT YET IMPLEMENTED
1. **Panda3D 3D Renderer** — Main app, scene, turret model, target models, camera (orbit)
2. **Visual Effects** — Muzzle flash, tracers, explosion on hit, barrel smoke on overheat
3. **Sound System** — Firing, hit, servo motors
4. **HUD/UI** — Ammo counter, heat bar, weather panel, score, round info
5. **Monocular PIP** — Picture-in-picture scope view with crosshair (separate camera)
6. **Manual Controls** — Mouse/keyboard turret aiming alongside API control
7. **Example Scripts** — Python scripts using REST API: simple aim, lead calculation
8. **Asset Generation** — Procedural geometry for turret, targets, ground, trees

## SPECIFICATIONS

### Turret — Browning M2HB
- Caliber: 12.7×99mm NATO (.50 BMG)
- Dual-barrel (twin mount), alternating fire
- Rate of fire: ~485 RPM cyclic
- Belt: 100 rounds, ~8s reload
- Muzzle velocity: 890 m/s
- Traverse: 360° at 60°/s, Elevation: -15° to +85° at 40°/s
- Overheat after ~200 rounds sustained

### Ballistics (MAXIMUM PRIORITY — must be mathematically accurate)
- G7 ballistic tables (boat-tail reference), BC = 0.337
- Form factor scaling: i = SD/BC
- Drag: Cd(Mach) from G7 table × form factor × 0.5 × ρ × v² × A / m
- Gravity: -9.80665 m/s² (Z-down)
- Wind: constant vector per round, affects via v_relative = v_bullet - v_wind
- Magnus/spin drift: empirical Litz model, ~15cm at 1000m
- Coriolis: Ω_ENU = ω × (0, cos(lat), sin(lat)), a = -2(Ω×v)
- Air density: full humidity correction (moist air is lighter)
- Speed of sound: temperature + humidity corrected
- Integration: RK4, dt=0.001s

### Targets
- Aerial only, one at a time, straight trajectories
- Types: drone (20-60 m/s), light aircraft (50-120), helicopter (30-80), cruise missile (200-300)
- One-hit destruction
- Round-based with score tracking

### API
- REST (Flask): /status, /target, /aim, /fire/start, /fire/stop, /reload, /game, /weather, /ballistics
- WebSocket: push events (round_fired, target_hit, overheat, reload, round_start/end)
- Monocular challenge: /target returns angular info ONLY when target is in scope FOV

### Scene
- Flat ground polygon, trees on horizon
- Orbit camera around turret (mouse drag)
- Weather panel in UI
- Monocular PIP window with crosshair (no HUD data — just scope + crosshair)

### Effects
- Muzzle flash (light + particle)
- Tracers (every bullet visible)
- Explosion on target hit
- Barrel smoke when overheated
- Sound: firing, hit/explosion, servo motors

### Controls
- Mouse/keyboard for manual aiming + fire (ALONGSIDE API, not instead of)
- API for scripted control

## COORDINATE SYSTEM
ENU: X=East, Y=North, Z=Up. Turret at origin. Azimuth: 0=North, CW positive.

## TECH STACK
- Python 3.12
- Panda3D 1.10.16 (open-source, NOT commercial)
- Flask + flask-cors (REST API)
- websockets (WS events)
- numpy (math)

## CURRENT STATUS
Core logic modules written and tested. Ballistics engine validated (4.7km at 45°, 2.9km at 5°). 
**Next step: Panda3D application with 3D rendering, then layer in effects, HUD, controls, and example scripts.**

## IMPORTANT NOTES
- There are duplicate/old files from earlier iterations (physics/, server/, client/). The canonical modules are in ballistics/, turret/, targets/, game/, api/. Clean up the old files.
- MVP level — working prototype, not production polish
- Ballistic accuracy is the #1 priority over everything else

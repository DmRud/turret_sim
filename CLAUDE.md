# Turret Simulator — Project Context for Claude Code

## PROJECT OVERVIEW
Realistic ballistics turret simulator: Browning M2HB (.50 BMG) dual-mounted on M3 tripod engaging aerial targets. Desktop application with Python + Panda3D.

## ARCHITECTURE

### Core Modules (IMPLEMENTED — need review/cleanup)
- `ballistics/tables.py` — G1/G7 drag coefficient tables, .50 BMG M33 projectile data
- `ballistics/atmosphere.py` — ICAO atmosphere model (temperature, pressure, humidity → air density, speed of sound)
- `ballistics/engine.py` — Full ballistic simulation: RK4 integrator, gravity, G7 drag, Magnus effect, Coriolis effect, wind
- `turret/model.py` — M2HB mechanical model: traverse/elevation rates, heat, ammo, reload, twin barrel alternation
- `targets/manager.py` — Shahed-136 target spawning, straight-line trajectories
- `game/manager.py` — Round-based gameplay: weather generation, scoring, statistics, training mode
- `api/rest_server.py` — Flask REST API for external script control (runs in thread)
- `api/ws_server.py` — WebSocket event broadcaster for push notifications

### IMPLEMENTED
1. **Panda3D 3D Renderer** — Main app, scene, procedural turret model, orbit + first-person camera
2. **Monocular PIP** — Independent scope camera parented to turret pitch node, 5° FOV, thermal imaging mode (V)
3. **Manual Controls** — Arrow/WASD (simultaneous X+Y via polling), Space fire, R reload, T training, C camera toggle
4. **Procedural Geometry** — Turret (barrels, cradle, tripod, scope), environment (ground, trees, sky dome, clouds, fog)
5. **Shahed-136 3D Model** — Geranium-2 drone loaded from `assets/shahed/Geranium2.egg` with BaseColor texture
6. **DevTools Panel** — Permanent right sidebar (] toggle): turret telemetry, target info, weather, debug toggles, performance
7. **HUD** — Game state, ammo, heat bar, orientation, target info (range/altitude/bearing/speed), weather, stats, camera mode
8. **Visual Effects** — Muzzle flash (billboard sprites), bullet tracers (line segments), explosion on hit (animated sphere)
9. **Training Mode** — Static Shahed-136 at 200m altitude/200m range, respawns 3s after hit
10. **First-Person Camera** — Operator POV behind turret, mouse aiming, cursor lock

### NOT YET IMPLEMENTED
1. **Sound System** — Firing, hit, servo motors
2. **Barrel smoke** — Visual effect on overheat
3. **Moving Shahed target** — Training mode with drone flying at realistic speed/altitude

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
- Integration: RK4, adaptive dt (0.001s transonic, 0.002s super/subsonic, 0.005s slow)
- Optimized: pure-Python math in hot path, dense Cd LUT, altitude density LUT (29× speedup)

### Targets — Shahed-136 Only
- Single target type: Shahed-136 / Geran-2 kamikaze drone
- Speed: 19–51 m/s (70–185 km/h), altitude: 60–2000m
- One at a time, straight-line trajectories, one-hit destruction
- Round-based with score tracking
- Training mode: static Shahed-136 at 200m altitude, 200m range, respawns 3s after hit

### Shahed-136 / Geran-2
Full specifications in `assets/shahed/SPECIFICATIONS.md`. Key parameters:
- **Dimensions**: 3.5m length, 2.5m wingspan, ~200 kg MTOW
- **Speed**: cruise 140–150 km/h (39–42 m/s), max 185 km/h (51 m/s)
- **Altitude**: cruise 700–2,000m, approach 60–200m, min 20m, ceiling 4,000m
- **Attack profile**: RATO launch → climb to 700–2,000m → cruise at 140 km/h → descend to 200m → terminal dive
- **Engine**: MADO MD-550 (50 hp piston, pusher), 2-blade propeller
- **Navigation**: INS + GPS, radio correction up to 150 km
- **RCS**: ~0.01–0.1 m² (very low, comparable to large bird)
- **3D Model**: `assets/shahed/Geranium2.egg` (EGG format, cm scale → 0.01x), BaseColor texture applied

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
- Arrow/WASD: turret aiming (simultaneous X+Y via KeyboardButton polling)
- Space: fire, R: reload, Enter: start/next round, T: training mode
- LMB/MMB drag: orbit camera, Scroll: zoom
- C: first-person / orbit camera toggle
- V: scope thermal imaging toggle
- ]: debug panel (visible by default), ESC: quit
- API for scripted control (alongside manual)

## COORDINATE SYSTEM
ENU: X=East, Y=North, Z=Up. Turret at origin. Azimuth: 0=North, CW positive.

## TECH STACK
- Python 3.12
- Panda3D 1.10.16 (open-source, NOT commercial)
- Flask + flask-cors (REST API)
- websockets (WS events)
- numpy (math)

## CURRENT STATUS
Working Panda3D application with full 3D rendering, Shahed-136 drone model, scope PIP with thermal imaging, DevTools panel, HUD with target telemetry, muzzle flash, tracers, explosions, first-person camera, and optimized ballistics engine. Ballistics validated (4.7km at 45°, 2.9km at 5°).
**Next step: Sound system, moving Shahed target with realistic flight profile, barrel smoke effect.**

## IMPORTANT NOTES
- MVP level — working prototype, not production polish
- Ballistic accuracy is the #1 priority over everything else

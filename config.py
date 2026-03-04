"""
Turret Simulator — Configuration

All tunable parameters, keybindings, and visual coefficients in one place.
Edit values here instead of hunting through app.py.
"""

# ═══════════════════════════════════════════════════════════════
# KEYBINDINGS
# ═══════════════════════════════════════════════════════════════

KEYS = {
    "reload": "r",
    "start": "enter",
    "training": "t",
    "camera_toggle": "c",
    "thermal": "v",
    "night_mode": "n",
    "debug_panel": "]",
    "quit": "escape",
}

# ═══════════════════════════════════════════════════════════════
# STARTUP DEFAULTS
# ═══════════════════════════════════════════════════════════════

START_NIGHT_MODE = True        # True = start in night, False = start in day
START_FIRST_PERSON = True      # True = start in FP scope, False = orbit camera

# ═══════════════════════════════════════════════════════════════
# CAMERA — Orbit
# ═══════════════════════════════════════════════════════════════

CAM_DISTANCE = 12.0        # initial orbit distance (m)
CAM_HEADING = 30.0         # initial heading (degrees)
CAM_PITCH = -25.0          # initial pitch (degrees)
CAM_TARGET = (0, 0, 1.2)  # orbit target point
CAM_ZOOM_MIN = 3.0         # closest zoom (m)
CAM_ZOOM_MAX = 50.0        # farthest zoom (m)
CAM_ZOOM_STEP = 0.8        # scroll step (m)
CAM_DRAG_H_SENS = 100.0   # mouse drag → heading (deg/unit)
CAM_DRAG_P_SENS = 60.0    # mouse drag → pitch (deg/unit)
CAM_PITCH_MIN = -85.0      # orbit pitch lower bound
CAM_PITCH_MAX = 85.0       # orbit pitch upper bound

# ═══════════════════════════════════════════════════════════════
# CAMERA — First-person scope
# ═══════════════════════════════════════════════════════════════

FP_FOV = 15.0              # first-person scope FOV (degrees)
FP_NEAR = 0.1              # near clip
FP_FAR = 10000.0           # far clip
FP_MOUSE_SENS = 0.4        # degrees per unit of mouse offset
FP_CAM_OFFSET = (0, -0.35, 0.30)  # position relative to pitch node

# ═══════════════════════════════════════════════════════════════
# TURRET CONTROL
# ═══════════════════════════════════════════════════════════════

MANUAL_AIM_SPEED = 15.0    # keyboard aiming rate (deg/s)
VERTICAL_SPEED_MULT = 0.7  # elevation speed multiplier

# ═══════════════════════════════════════════════════════════════
# SCOPE / PIP
# ═══════════════════════════════════════════════════════════════

SCOPE_FOV = 5.0            # monocular PIP FOV (degrees)
SCOPE_NEAR = 0.1
SCOPE_FAR = 10000.0
SCOPE_TEX_SIZE = 256       # offscreen buffer resolution

# ═══════════════════════════════════════════════════════════════
# LIGHTING — Day
# ═══════════════════════════════════════════════════════════════

DAY_AMBIENT = (0.3, 0.3, 0.35, 1)
DAY_SUN = (1.0, 0.95, 0.85, 1)
DAY_FILL = (0.3, 0.35, 0.4, 1)
DAY_BG = (0.78, 0.84, 0.92, 1)
DAY_FOG_COLOR = (0.75, 0.82, 0.90)
DAY_FOG_DENSITY = 0.0015

# ═══════════════════════════════════════════════════════════════
# LIGHTING — Night
# ═══════════════════════════════════════════════════════════════

NIGHT_AMBIENT = (0.06, 0.06, 0.10, 1)
NIGHT_SUN = (0.10, 0.12, 0.18, 1)
NIGHT_FILL = (0.04, 0.05, 0.08, 1)
NIGHT_BG = (0.02, 0.02, 0.05, 1)
NIGHT_FOG_COLOR = (0.02, 0.02, 0.05)
NIGHT_FOG_DENSITY = 0.004

# ═══════════════════════════════════════════════════════════════
# SEARCHLIGHT
# ═══════════════════════════════════════════════════════════════

SL_COLOR = (50.0, 48.0, 40.0, 1)    # spotlight RGBA — very high lumens
SL_ATTENUATION = (1, 0, 0.00002)    # even slower falloff over distance
SL_EXPONENT = 128                    # high = strong circular cosine falloff
SL_FOV = 8.0                        # beam angle (degrees)
SL_SHADOW_RES = 1024                 # shadow map resolution

# ═══════════════════════════════════════════════════════════════
# BEAM VISUAL (volumetric cone)
# ═══════════════════════════════════════════════════════════════

BEAM_HALF_ANGLE_DEG = 2.0   # visual cone half-angle (degrees)
BEAM_APEX_ALPHA = 0.06      # brightness at spotlight origin
BEAM_BASE_ALPHA = 0.01      # brightness at target ring
BEAM_SLICES = 24             # triangle count in cone mesh
BEAM_SPLASH_MIN_SIZE = 8.0  # minimum splash radius on target (m)
BEAM_SPLASH_CORE_ALPHA = 0.9
BEAM_SPLASH_GLOW_ALPHA = 0.4

# ═══════════════════════════════════════════════════════════════
# MUZZLE FLASH
# ═══════════════════════════════════════════════════════════════

FLASH_DURATION = 0.03       # seconds per flash
FLASH_SCALE_MIN = 0.8       # random scale range
FLASH_SCALE_MAX = 1.8
FLASH_CORE_SIZE = 0.10      # core billboard half-size (m)
FLASH_GLOW_SIZE = 0.25      # outer glow half-size (m)
FLASH_GLOW_COLOR = (1.0, 0.6, 0.15, 0.5)
FLASH_LIGHT_COLOR = (8.0, 5.0, 1.5, 1)
FLASH_LIGHT_ATTEN = (1, 0.5, 0.5)
FLASH_TEX_SIZE = 128        # procedural starburst texture resolution

# ═══════════════════════════════════════════════════════════════
# TRACERS
# ═══════════════════════════════════════════════════════════════

TRACER_CORE_THICKNESS = 3.5  # pixels
TRACER_GLOW_THICKNESS = 8.0  # pixels
TRACER_TRAIL_LENGTH = 30     # number of trail positions

# ═══════════════════════════════════════════════════════════════
# EXPLOSION
# ═══════════════════════════════════════════════════════════════

EXPLOSION_DURATION = 2.0           # seconds
EXPLOSION_DEBRIS_COUNT = 12
EXPLOSION_DEBRIS_SPEED = (8, 25)   # min/max m/s
EXPLOSION_LIGHT_COLOR = (15, 10, 4, 1)
EXPLOSION_LIGHT_ATTEN = (1, 0.02, 0.002)

# ═══════════════════════════════════════════════════════════════
# TARGET MATERIAL (surface reflection)
# ═══════════════════════════════════════════════════════════════

TARGET_MAT_AMBIENT = (0.3, 0.3, 0.28, 1)
TARGET_MAT_DIFFUSE = (0.6, 0.6, 0.55, 1)
TARGET_MAT_SPECULAR = (0.7, 0.7, 0.65, 1)    # stronger specular for visible reflection
TARGET_MAT_SHININESS = 8                       # broader highlight = more visible

# ═══════════════════════════════════════════════════════════════
# TRUCK
# ═══════════════════════════════════════════════════════════════

TRUCK_SCALE = 0.0056
TRUCK_POS = (-0.020, 1.600, -0.520)
GROUND_Z = -0.520

# ═══════════════════════════════════════════════════════════════
# SOLDIERS
# ═══════════════════════════════════════════════════════════════

SOLDIER_SCALE = 0.01
GUNNER_OFFSET = (0, -0.45, -1.2)      # turret operator relative to yaw node
SL_SOLDIER_POS = (5.0, 0, -0.52)      # searchlight soldier world position
FLASHLIGHT_POS = (0.15, 0.35, 1.3)    # flashlight in soldier-local coords

# ═══════════════════════════════════════════════════════════════
# TRAINING TARGET (figure-eight path)
# ═══════════════════════════════════════════════════════════════

TRAINING_RADIUS = 500.0    # lobe radius (m)
TRAINING_OFFSET = 700.0    # center of eight, north of turret (m)
TRAINING_ALT = 200.0       # constant altitude (m)
TRAINING_SPEED = 40.0      # cruise speed (m/s)

# ═══════════════════════════════════════════════════════════════
# RADAR
# ═══════════════════════════════════════════════════════════════

RADAR_RADIUS = 0.18        # aspect2d units
RADAR_MAX_RANGE = 3000.0   # meters mapped to radar edge
RADAR_BG_COLOR = (0.05, 0.08, 0.05, 0.70)

# ═══════════════════════════════════════════════════════════════
# CLOUD
# ═══════════════════════════════════════════════════════════════

CLOUD_DRIFT_SPEED = 0.3    # degrees/second rotation

# ═══════════════════════════════════════════════════════════════
# PERFORMANCE
# ═══════════════════════════════════════════════════════════════

MAX_FRAME_DT = 0.05        # cap delta time to prevent physics jumps


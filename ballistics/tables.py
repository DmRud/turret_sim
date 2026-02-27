"""
G1 and G7 Standard Drag Coefficient Tables
Based on Ingalls/Mayevski ballistic tables and the G7 long-range standard.

The drag coefficient Cd varies with Mach number. These tables provide
Cd(Mach) for G1 (flat-base) and G7 (boat-tail, VLD) reference projectiles.

For the .50 BMG M33 Ball (12.7x99mm NATO):
  - G1 BC ~ 0.670
  - G7 BC ~ 0.337
  - We use G7 as primary (better match for boat-tail .50 BMG projectiles)
"""

import numpy as np
from typing import Tuple

# G1 Standard Drag Table: (Mach, Cd)
# Ingalls tables, widely published
G1_TABLE = np.array([
    [0.00, 0.2629],
    [0.05, 0.2558],
    [0.10, 0.2487],
    [0.15, 0.2413],
    [0.20, 0.2344],
    [0.25, 0.2278],
    [0.30, 0.2214],
    [0.35, 0.2155],
    [0.40, 0.2104],
    [0.45, 0.2061],
    [0.50, 0.2032],
    [0.55, 0.2020],
    [0.60, 0.2034],
    [0.65, 0.2165],
    [0.70, 0.2230],
    [0.75, 0.2313],
    [0.80, 0.2417],
    [0.85, 0.2546],
    [0.90, 0.2706],
    [0.925, 0.2838],
    [0.95, 0.3017],
    [0.975, 0.3237],
    [1.00, 0.3537],
    [1.025, 0.3860],
    [1.05, 0.4041],
    [1.075, 0.4147],
    [1.10, 0.4209],
    [1.125, 0.4248],
    [1.15, 0.4270],
    [1.175, 0.4280],
    [1.20, 0.4280],
    [1.25, 0.4263],
    [1.30, 0.4230],
    [1.35, 0.4183],
    [1.40, 0.4127],
    [1.45, 0.4068],
    [1.50, 0.4008],
    [1.55, 0.3947],
    [1.60, 0.3887],
    [1.65, 0.3828],
    [1.70, 0.3770],
    [1.75, 0.3715],
    [1.80, 0.3663],
    [1.85, 0.3612],
    [1.90, 0.3564],
    [1.95, 0.3518],
    [2.00, 0.3474],
    [2.05, 0.3432],
    [2.10, 0.3392],
    [2.15, 0.3354],
    [2.20, 0.3318],
    [2.25, 0.3284],
    [2.30, 0.3251],
    [2.35, 0.3219],
    [2.40, 0.3188],
    [2.45, 0.3159],
    [2.50, 0.3131],
    [2.60, 0.3078],
    [2.70, 0.3029],
    [2.80, 0.2984],
    [2.90, 0.2943],
    [3.00, 0.2906],
    [3.10, 0.2872],
    [3.20, 0.2842],
    [3.30, 0.2814],
    [3.40, 0.2788],
    [3.50, 0.2764],
    [3.60, 0.2742],
    [3.70, 0.2721],
    [3.80, 0.2702],
    [3.90, 0.2684],
    [4.00, 0.2668],
    [4.20, 0.2638],
    [4.40, 0.2614],
    [4.60, 0.2594],
    [4.80, 0.2577],
    [5.00, 0.2563],
])

# G7 Standard Drag Table: (Mach, Cd)
# Better model for long-range boat-tail projectiles like .50 BMG
G7_TABLE = np.array([
    [0.00, 0.1198],
    [0.05, 0.1197],
    [0.10, 0.1196],
    [0.15, 0.1194],
    [0.20, 0.1193],
    [0.25, 0.1194],
    [0.30, 0.1194],
    [0.35, 0.1194],
    [0.40, 0.1193],
    [0.45, 0.1193],
    [0.50, 0.1194],
    [0.55, 0.1193],
    [0.60, 0.1194],
    [0.65, 0.1197],
    [0.70, 0.1202],
    [0.725, 0.1207],
    [0.75, 0.1215],
    [0.775, 0.1226],
    [0.80, 0.1242],
    [0.825, 0.1266],
    [0.85, 0.1306],
    [0.875, 0.1368],
    [0.90, 0.1464],
    [0.925, 0.1660],
    [0.95, 0.2054],
    [0.975, 0.2993],
    [1.00, 0.3803],
    [1.025, 0.4015],
    [1.05, 0.4043],
    [1.075, 0.4034],
    [1.10, 0.4014],
    [1.125, 0.3987],
    [1.15, 0.3955],
    [1.20, 0.3884],
    [1.25, 0.3810],
    [1.30, 0.3732],
    [1.35, 0.3657],
    [1.40, 0.3580],
    [1.50, 0.3440],
    [1.55, 0.3376],
    [1.60, 0.3315],
    [1.65, 0.3260],
    [1.70, 0.3209],
    [1.75, 0.3160],
    [1.80, 0.3117],
    [1.85, 0.3078],
    [1.90, 0.3042],
    [1.95, 0.3010],
    [2.00, 0.2980],
    [2.05, 0.2951],
    [2.10, 0.2922],
    [2.15, 0.2892],
    [2.20, 0.2864],
    [2.25, 0.2835],
    [2.30, 0.2807],
    [2.35, 0.2779],
    [2.40, 0.2752],
    [2.45, 0.2725],
    [2.50, 0.2697],
    [2.55, 0.2670],
    [2.60, 0.2643],
    [2.65, 0.2615],
    [2.70, 0.2588],
    [2.75, 0.2561],
    [2.80, 0.2533],
    [2.85, 0.2506],
    [2.90, 0.2479],
    [2.95, 0.2451],
    [3.00, 0.2424],
    [3.10, 0.2368],
    [3.20, 0.2313],
    [3.30, 0.2258],
    [3.40, 0.2205],
    [3.50, 0.2154],
    [3.60, 0.2106],
    [3.70, 0.2060],
    [3.80, 0.2017],
    [3.90, 0.1975],
    [4.00, 0.1935],
    [4.20, 0.1861],
    [4.40, 0.1793],
    [4.60, 0.1730],
    [4.80, 0.1672],
    [5.00, 0.1618],
])


class DragModel:
    """
    Interpolates drag coefficient from standard ballistic tables.
    Supports G1 and G7 models.

    Uses a precomputed dense uniform-step table for O(1) lookup
    instead of binary-search-based np.interp on every call.
    """

    # Dense table parameters
    _MACH_STEP = 0.005   # Mach increment (1001 entries for 0.0–5.0)
    _MACH_MAX_DENSE = 5.0
    _DENSE_SIZE = 1001   # int(5.0 / 0.005) + 1

    def __init__(self, model: str = "G7"):
        if model.upper() == "G1":
            self.table = G1_TABLE
        elif model.upper() == "G7":
            self.table = G7_TABLE
        else:
            raise ValueError(f"Unknown drag model: {model}. Use 'G1' or 'G7'.")

        self.model = model.upper()
        self.mach_values = self.table[:, 0]
        self.cd_values = self.table[:, 1]
        self.mach_min = float(self.mach_values[0])
        self.mach_max = float(self.mach_values[-1])

        # Precompute dense uniform table for O(1) lookup
        dense_mach = np.linspace(0.0, self._MACH_MAX_DENSE, self._DENSE_SIZE)
        self._cd_dense = np.interp(dense_mach, self.mach_values, self.cd_values)
        # Store as plain Python list for fastest scalar indexing
        self._cd_list = self._cd_dense.tolist()
        self._inv_step = 1.0 / self._MACH_STEP  # = 200.0

    def get_cd(self, mach: float) -> float:
        """
        O(1) drag coefficient lookup via dense precomputed table.
        Linear interpolation between two nearest entries.
        """
        if mach <= 0.0:
            return self._cd_list[0]
        if mach >= self._MACH_MAX_DENSE:
            return self._cd_list[-1]

        idx_f = mach * self._inv_step
        idx = int(idx_f)
        frac = idx_f - idx
        return self._cd_list[idx] + frac * (self._cd_list[idx + 1] - self._cd_list[idx])

    def get_cd_array(self, mach_array: np.ndarray) -> np.ndarray:
        """Vectorized Cd lookup for arrays of Mach numbers."""
        mach_clamped = np.clip(mach_array, self.mach_min, self.mach_max)
        return np.interp(mach_clamped, self.mach_values, self.cd_values)


# ---- .50 BMG M33 Ball Projectile Data ----
# Reference: Litz "Applied Ballistics" & military TM data

PROJECTILE_50BMG = {
    "name": "12.7x99mm NATO M33 Ball",
    "caliber_mm": 12.7,
    "caliber_m": 0.0127,
    "mass_kg": 0.04174,          # 647 grains = 41.74 grams
    "mass_grains": 647.0,
    "diameter_m": 0.0127,         # bore diameter
    "bc_g1": 0.670,               # G1 ballistic coefficient (lb/in²)
    "bc_g7": 0.337,               # G7 ballistic coefficient (lb/in²)
    "muzzle_velocity_mps": 890.0, # m/s (2920 fps)
    "twist_rate_inches": 15.0,    # 1:15" right-hand twist (M2)
    "twist_direction": 1,         # +1 = right-hand, -1 = left-hand
    "length_calibers": 4.65,      # bullet length in calibers
    "sectional_density": 0.412,   # SD = mass / diameter^2 (in lb/in²)
}

# Cross-sectional area of the projectile
PROJECTILE_50BMG["cross_section_m2"] = np.pi * (PROJECTILE_50BMG["diameter_m"] / 2) ** 2


def bc_to_form_factor(bc: float, sectional_density: float) -> float:
    """
    Convert ballistic coefficient to form factor.
    i = SD / BC
    Form factor relates actual projectile drag to the standard reference.
    """
    return sectional_density / bc


# Pre-compute form factor for .50 BMG with G7
PROJECTILE_50BMG["form_factor_g7"] = bc_to_form_factor(
    PROJECTILE_50BMG["bc_g7"],
    PROJECTILE_50BMG["sectional_density"]
)

PROJECTILE_50BMG["form_factor_g1"] = bc_to_form_factor(
    PROJECTILE_50BMG["bc_g1"],
    PROJECTILE_50BMG["sectional_density"]
)

"""
Atmospheric Model for Ballistic Calculations

Implements the ICAO Standard Atmosphere model with corrections for
non-standard temperature, pressure, and humidity.

Used to compute:
  - Air density (rho) — affects drag force
  - Speed of sound — needed for Mach number calculation
  - Density ratio — for altitude corrections

Reference conditions (ICAO ISA at sea level):
  - Temperature: 15°C (288.15 K)
  - Pressure: 101325 Pa (29.92 inHg)
  - Humidity: 0% (dry air)
  - Density: 1.225 kg/m³
  - Speed of sound: 340.3 m/s
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple


# Physical constants
R_DRY = 287.058      # Specific gas constant for dry air, J/(kg·K)
R_VAPOR = 461.495    # Specific gas constant for water vapor, J/(kg·K)
GAMMA_AIR = 1.4      # Ratio of specific heats for air
LAPSE_RATE = 0.0065  # Temperature lapse rate, K/m (troposphere)
G_STD = 9.80665      # Standard gravity, m/s²

# ISA standard conditions at sea level
ISA_TEMP_K = 288.15      # 15°C
ISA_PRESSURE_PA = 101325  # Pa
ISA_DENSITY = 1.225       # kg/m³
ISA_SPEED_OF_SOUND = 340.294  # m/s


@dataclass
class WeatherConditions:
    """Weather parameters for a round."""
    temperature_c: float = 15.0       # Celsius
    pressure_hpa: float = 1013.25     # hectopascals (millibars)
    humidity_pct: float = 50.0        # relative humidity, 0-100%
    wind_speed_mps: float = 0.0       # wind speed, m/s
    wind_direction_deg: float = 0.0   # wind FROM direction, degrees (0=N, 90=E)
    altitude_m: float = 0.0           # altitude above sea level
    
    @property
    def temperature_k(self) -> float:
        return self.temperature_c + 273.15
    
    @property
    def pressure_pa(self) -> float:
        return self.pressure_hpa * 100.0
    
    @property
    def wind_vector(self) -> np.ndarray:
        """
        Wind vector in world coordinates (X=East, Y=North, Z=Up).
        Wind direction is where wind comes FROM, so we negate.
        """
        rad = np.radians(self.wind_direction_deg)
        # Wind FROM north (0°) means wind blows south (-Y)
        wx = -self.wind_speed_mps * np.sin(rad)  # East component
        wy = -self.wind_speed_mps * np.cos(rad)  # North component
        wz = 0.0  # No vertical wind
        return np.array([wx, wy, wz])


class AtmosphereModel:
    """
    Computes atmospheric properties based on weather conditions.
    """
    
    def __init__(self, weather: WeatherConditions = None):
        self.weather = weather or WeatherConditions()
        self._update_cache()
    
    def set_weather(self, weather: WeatherConditions):
        self.weather = weather
        self._update_cache()
    
    # Density LUT parameters
    _DENSITY_LUT_STEP = 10.0    # meters per bin
    _DENSITY_LUT_MAX = 5000.0   # max altitude in LUT
    _DENSITY_LUT_SIZE = 501     # int(5000/10) + 1

    def _update_cache(self):
        """Pre-compute cached atmospheric values and density LUT."""
        w = self.weather
        self._air_density = self._compute_air_density(
            w.temperature_k, w.pressure_pa, w.humidity_pct
        )
        self._speed_of_sound = self._compute_speed_of_sound(
            w.temperature_k, w.humidity_pct
        )
        self._density_ratio = self._air_density / ISA_DENSITY

        # Build density lookup table by altitude (O(1) access per query)
        self._density_lut = []
        hum = w.humidity_pct
        for i in range(self._DENSITY_LUT_SIZE):
            alt = i * self._DENSITY_LUT_STEP
            T, P = self.altitude_correction(alt)
            self._density_lut.append(self._compute_air_density(T, P, hum))
        self._density_inv_step = 1.0 / self._DENSITY_LUT_STEP  # = 0.1
    
    @property
    def air_density(self) -> float:
        """Current air density in kg/m³."""
        return self._air_density
    
    @property
    def speed_of_sound(self) -> float:
        """Current speed of sound in m/s."""
        return self._speed_of_sound
    
    @property
    def density_ratio(self) -> float:
        """Ratio of current density to ISA standard density."""
        return self._density_ratio
    
    def get_mach(self, velocity_mps: float) -> float:
        """Convert velocity in m/s to Mach number."""
        return velocity_mps / self._speed_of_sound
    
    @staticmethod
    def _saturation_vapor_pressure(temp_k: float) -> float:
        """
        Saturation vapor pressure using Magnus-Tetens formula.
        Returns pressure in Pa.
        """
        temp_c = temp_k - 273.15
        # Buck equation (more accurate than simple Magnus)
        return 611.21 * np.exp((18.678 - temp_c / 234.5) * (temp_c / (257.14 + temp_c)))
    
    @staticmethod
    def _compute_air_density(temp_k: float, pressure_pa: float, 
                              humidity_pct: float) -> float:
        """
        Compute air density accounting for humidity.
        Humid air is LESS dense than dry air (water vapor is lighter than N2/O2).
        
        Uses the equation of state for moist air:
        rho = (p_d / (R_d * T)) + (p_v / (R_v * T))
        where p_d = dry air partial pressure, p_v = vapor pressure
        """
        # Vapor pressure
        e_sat = AtmosphereModel._saturation_vapor_pressure(temp_k)
        e = (humidity_pct / 100.0) * e_sat  # Actual vapor pressure
        
        # Partial pressure of dry air
        p_dry = pressure_pa - e
        
        # Density = dry air density + vapor density
        rho = (p_dry / (R_DRY * temp_k)) + (e / (R_VAPOR * temp_k))
        return rho
    
    @staticmethod
    def _compute_speed_of_sound(temp_k: float, humidity_pct: float) -> float:
        """
        Speed of sound in moist air.
        
        For dry air: c = sqrt(gamma * R * T)
        Humidity slightly increases speed of sound (lower molecular weight).
        Approximate correction for humidity.
        """
        # Dry air speed of sound
        c_dry = np.sqrt(GAMMA_AIR * R_DRY * temp_k)
        
        # Humidity correction (approximate - up to ~0.5% at 100% RH)
        e_sat = AtmosphereModel._saturation_vapor_pressure(temp_k)
        e = (humidity_pct / 100.0) * e_sat
        
        # Mole fraction of water vapor
        x_v = e / (e + (101325 - e))  # approximate
        
        # Corrected gamma for moist air (approximate)
        # Water vapor has gamma=1.33 vs air gamma=1.4
        gamma_moist = GAMMA_AIR - 0.07 * x_v
        
        # Corrected molecular weight effect
        # M_air=28.97, M_water=18.015 -> lighter mixture = faster sound
        R_moist = R_DRY * (1 + (R_VAPOR / R_DRY - 1) * x_v)
        
        c = np.sqrt(gamma_moist * R_moist * temp_k)
        return c
    
    def altitude_correction(self, altitude_m: float) -> Tuple[float, float]:
        """
        Compute temperature and pressure at altitude using
        the barometric formula (troposphere only).
        
        Returns (temperature_K, pressure_Pa) at altitude.
        """
        T0 = self.weather.temperature_k
        P0 = self.weather.pressure_pa
        
        T = T0 - LAPSE_RATE * altitude_m
        P = P0 * (T / T0) ** (G_STD / (LAPSE_RATE * R_DRY))
        
        return T, P
    
    def density_at_altitude(self, altitude_m: float) -> float:
        """Air density at a given altitude above the firing point.

        Uses precomputed LUT with linear interpolation for O(1) access.
        Falls back to full calculation for altitudes above LUT range.
        """
        if altitude_m <= 0.0:
            return self._density_lut[0]
        if altitude_m >= self._DENSITY_LUT_MAX:
            # Rare: above 5 km — compute directly
            T, P = self.altitude_correction(altitude_m)
            return self._compute_air_density(T, P, self.weather.humidity_pct)

        idx_f = altitude_m * self._density_inv_step
        idx = int(idx_f)
        frac = idx_f - idx
        return self._density_lut[idx] + frac * (self._density_lut[idx + 1] - self._density_lut[idx])


def generate_random_weather() -> WeatherConditions:
    """Generate random but realistic weather conditions for a round."""
    return WeatherConditions(
        temperature_c=np.random.uniform(-10, 40),
        pressure_hpa=np.random.uniform(990, 1040),
        humidity_pct=np.random.uniform(10, 95),
        wind_speed_mps=np.random.uniform(0, 15),
        wind_direction_deg=np.random.uniform(0, 360),
        altitude_m=np.random.choice([0, 100, 500, 1000, 1500]),
    )

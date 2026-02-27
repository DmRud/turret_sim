#!/usr/bin/env python3
"""
Example 2: Lead Prediction
Predicts where the target will be when the bullet arrives.
Accounts for:
- Target velocity and direction
- Approximate bullet time of flight
- Iterative lead refinement

Usage:
    python example_lead_prediction.py
"""

import sys
import os
import time
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from client.turret_client import TurretClient


# Approximate .50 BMG ballistics for lead calculation
MUZZLE_VELOCITY = 890.0  # m/s
DRAG_COEFF = 0.0004      # Simplified drag for TOF estimation


def estimate_tof(distance: float) -> float:
    """
    Estimate time of flight to a given distance.
    Uses simplified drag model: v(t) = v0 * exp(-k*t)
    TOF ≈ distance / avg_velocity
    """
    if distance < 1:
        return 0.0
    # Average velocity accounting for drag
    # At 1000m, .50 BMG retains ~70% velocity
    avg_v = MUZZLE_VELOCITY * math.exp(-DRAG_COEFF * distance)
    avg_v = (MUZZLE_VELOCITY + avg_v) / 2
    return distance / avg_v


def predict_target_position(target_info: dict, tof: float):
    """Predict where target will be after 'tof' seconds."""
    # Position and velocity are lists [x, y, z] in ENU (East, North, Up)
    pos = target_info["position"]
    vel = target_info["velocity"]
    x = pos[0] + vel[0] * tof
    y = pos[1] + vel[1] * tof
    z = pos[2] + vel[2] * tof
    return x, y, z


def pos_to_aim(x, y, z) -> tuple:
    """Convert ENU position to azimuth/elevation angles (degrees)."""
    # ENU: X=East, Y=North, Z=Up
    horiz_dist = math.sqrt(x**2 + y**2)
    azimuth = math.degrees(math.atan2(x, y))  # atan2(East, North)
    elevation = math.degrees(math.atan2(z, horiz_dist))
    return azimuth, elevation


def gravity_compensation(distance: float, elevation_deg: float) -> float:
    """
    Compensate for bullet drop.
    Returns additional elevation in degrees.
    """
    if distance < 10:
        return 0.0

    tof = estimate_tof(distance)
    # Bullet drop = 0.5 * g * t^2
    drop = 0.5 * 9.81 * tof**2

    # Convert drop to angle
    drop_angle = math.degrees(math.atan2(drop, distance))
    return drop_angle


def main():
    client = TurretClient()

    # Event handler
    hits = 0
    misses = 0

    def on_event(event):
        nonlocal hits, misses
        etype = event.get("type")
        if etype == "target_hit":
            hits += 1
            print(f"\n  >>> HIT! ({hits} hits, {misses} misses) "
                  f"Time: {event.get('time', '?')}s")
        elif etype == "target_escaped":
            misses += 1
            print(f"\n  >>> ESCAPED! ({hits} hits, {misses} misses)")
        elif etype == "overheated":
            print("\n  >>> OVERHEATED - cooling down...")

    client.on_event(on_event)

    print("Lead Prediction Tracking Script")
    print("=" * 50)
    print("Uses bullet TOF estimation + target velocity")
    print("for predictive aiming.\n")

    # Start game
    client.start_game()
    time.sleep(4)

    iteration = 0

    while True:
        try:
            status = client.get_game()
            game_state = status.get("game_state")

            if game_state in ("target_hit", "target_escaped"):
                time.sleep(0.1)
                continue

            if game_state == "round_end":
                print(f"\nRound done. Score: {hits}/{hits+misses}")
                time.sleep(2)
                client.next_round()
                time.sleep(4)
                continue

            if game_state != "playing":
                time.sleep(0.1)
                continue

            target = status.get("target")
            if not target:
                time.sleep(0.1)
                continue

            # === LEAD PREDICTION (iterative) ===
            distance = target["range_m"]

            # Iterative refinement: estimate TOF, predict position,
            # recalculate distance, repeat
            pos = target["position"]  # [x, y, z] ENU
            pred_x, pred_y, pred_z = pos[0], pos[1], pos[2]

            for _ in range(3):  # 3 iterations is usually enough
                tof = estimate_tof(
                    math.sqrt(pred_x**2 + pred_y**2 + pred_z**2))
                pred_x, pred_y, pred_z = predict_target_position(target, tof)

            # Convert predicted position to aim angles
            azimuth, elevation = pos_to_aim(pred_x, pred_y, pred_z)

            # Add gravity compensation
            pred_dist = math.sqrt(pred_x**2 + pred_y**2 + pred_z**2)
            grav_comp = gravity_compensation(pred_dist, elevation)
            elevation += grav_comp

            # Clamp elevation
            elevation = max(10.0, min(85.0, elevation))

            # Rotate turret
            client.rotate(azimuth, elevation)

            # Check if we should fire
            turret = status.get("turret", {})
            az_err = abs(turret["azimuth_deg"] - azimuth)
            el_err = abs(turret["elevation_deg"] - elevation)

            # Fire when close to aim point (tighter threshold for accuracy)
            should_fire = az_err < 2 and el_err < 2

            if should_fire:
                client.fire(True)
            else:
                client.fire(False)

            # Display
            if iteration % 5 == 0:
                target_bearing = target.get("bearing_deg", 0)
                print(f"\r  Dist: {distance:.0f}m | "
                      f"TOF: {tof*1000:.0f}ms | "
                      f"Lead: az={azimuth - target_bearing:.1f}\u00b0 "
                      f"el={grav_comp:.2f}\u00b0 | "
                      f"Aim err: {az_err:.1f}\u00b0/{el_err:.1f}\u00b0 | "
                      f"{'FIRING' if should_fire else 'aiming'}  ",
                      end="", flush=True)

            iteration += 1
            time.sleep(0.033)  # ~30Hz

        except KeyboardInterrupt:
            print(f"\n\nFinal score: {hits}/{hits+misses}")
            client.fire(False)
            client.close()
            break
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(0.5)


if __name__ == "__main__":
    main()

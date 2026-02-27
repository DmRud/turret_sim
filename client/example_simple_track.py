#!/usr/bin/env python3
"""
Example 1: Simple Tracking
Aims directly at the target (no lead compensation).
Good for slow/close targets only.

Usage:
    python example_simple_track.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from client.turret_client import TurretClient


def main():
    client = TurretClient()

    # Subscribe to events
    def on_event(event):
        etype = event.get("type")
        if etype == "target_hit":
            print(f"  >>> TARGET HIT! Time: {event.get('time', '?')}s, "
                  f"Rounds: {event.get('rounds_fired', '?')}")
        elif etype == "target_escaped":
            print("  >>> Target escaped!")
        elif etype == "overheated":
            print("  >>> Turret OVERHEATED!")

    client.on_event(on_event)

    print("Simple Tracking Script")
    print("=" * 40)

    # Start game
    print("Starting game...")
    client.start_game()
    time.sleep(4)  # Wait for countdown

    while True:
        try:
            status = client.get_game()
            game_state = status.get("game_state")

            if game_state == "round_end":
                print("\nRound complete. Starting next round...")
                time.sleep(1)
                client.next_round()
                time.sleep(4)  # Countdown
                continue

            if game_state != "playing":
                time.sleep(0.1)
                continue

            target = status.get("target")
            if not target:
                time.sleep(0.1)
                continue

            # Aim directly at target (no lead)
            bearing = target["bearing_deg"]
            elevation = target["elevation_deg"]

            # Bearing is already in -180..180 range (atan2)
            azimuth = bearing

            print(f"\r  Target: dist={target['range_m']:.0f}m "
                  f"bear={bearing:.1f}\u00b0 elev={elevation:.1f}\u00b0 "
                  f"speed={target['speed_mps']:.0f}m/s",
                  end="", flush=True)

            client.rotate(azimuth, elevation)

            # Fire when roughly on target
            turret = status.get("turret", {})
            az_err = abs(turret["azimuth_deg"] - azimuth)
            el_err = abs(turret["elevation_deg"] - elevation)

            if az_err < 3 and el_err < 3:
                client.fire(True)
            else:
                client.fire(False)

            time.sleep(0.05)  # 20Hz update

        except KeyboardInterrupt:
            print("\n\nStopping...")
            client.fire(False)
            client.close()
            break
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(0.5)


if __name__ == "__main__":
    main()

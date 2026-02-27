"""
Audio Manager — Sound effects for turret simulator.

Stub implementation for MVP. All methods are no-ops.
When ready, integrate Panda3D's AudioManager for 3D positional audio.

Planned sounds:
  - Firing: M2HB burst (heavy, rhythmic)
  - Hit/Explosion: Impact + fireball
  - Servo motors: Electric slew sound when turret rotates
  - Reload: Belt change clank
  - Overheat: Sizzle / warning tone
"""


class AudioManager:
    """Stub audio manager — all no-ops for now."""

    def __init__(self, base=None):
        """
        Args:
            base: Panda3D ShowBase instance (for future Panda3D audio integration).
        """
        self.base = base
        self.enabled = False

    def play_fire(self):
        """Play M2HB firing sound."""
        pass

    def play_hit(self):
        """Play target hit / explosion sound."""
        pass

    def play_servo(self):
        """Play turret servo motor sound (loop while rotating)."""
        pass

    def stop_servo(self):
        """Stop turret servo motor sound."""
        pass

    def play_reload(self):
        """Play belt reload sound."""
        pass

    def play_overheat(self):
        """Play overheat warning sound."""
        pass

    def play_round_start(self):
        """Play round start chime."""
        pass

    def on_event(self, event: dict):
        """
        Dispatch game events to audio.
        Called from app.py _on_game_event().
        """
        etype = event.get("type", "")
        if etype == "shot_fired":
            self.play_fire()
        elif etype == "target_hit":
            self.play_hit()
        elif etype == "reload_start":
            self.play_reload()
        elif etype == "overheat":
            self.play_overheat()
        elif etype == "round_start":
            self.play_round_start()

    def update(self, dt: float):
        """Per-frame update (e.g. fade, loop management)."""
        pass

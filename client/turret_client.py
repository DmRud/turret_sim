"""
Turret Simulator - Python Client SDK

Usage:
    from turret_client import TurretClient
    
    client = TurretClient()
    client.start_game()
    
    # Get status
    status = client.get_status()
    
    # Rotate turret
    client.rotate(azimuth=45.0, elevation=30.0)
    
    # Fire
    client.fire(True)
    time.sleep(0.5)
    client.fire(False)
    
    # Events via WebSocket
    client.on_event(lambda e: print(e))
"""

import time
import json
import threading
from typing import Callable, Optional, Dict, Any

import httpx


class TurretClient:
    """
    Client SDK for the Turret Simulator REST API.
    """

    def __init__(self, host: str = "localhost", api_port: int = 8420,
                 ws_port: int = 8421):
        self.base_url = f"http://{host}:{api_port}"
        self.ws_url = f"ws://{host}:{ws_port}"
        self._http = httpx.Client(base_url=self.base_url, timeout=5.0)
        self._event_thread: Optional[threading.Thread] = None
        self._event_callback: Optional[Callable] = None
        self._ws_running = False

    def _get(self, path: str) -> dict:
        resp = self._http.get(path)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict = None) -> dict:
        resp = self._http.post(path, json=data or {})
        resp.raise_for_status()
        return resp.json()

    # === Game Control ===

    def start_game(self) -> dict:
        """Start a new game."""
        return self._post("/game/start")

    def next_round(self) -> dict:
        """Advance to next round."""
        return self._post("/game/next")

    # === Turret Control ===

    def rotate(self, azimuth: float, elevation: float) -> dict:
        """
        Set turret target orientation.

        Args:
            azimuth: Target azimuth in degrees (-180 to 180, 0=North)
            elevation: Target elevation in degrees (-15 to 85)
        """
        return self._post("/aim", {
            "azimuth_deg": azimuth,
            "elevation_deg": elevation,
        })

    def fire(self, firing: bool = True) -> dict:
        """
        Start or stop firing.

        Args:
            firing: True to start, False to stop
        """
        if firing:
            return self._post("/fire/start")
        else:
            return self._post("/fire/stop")

    def reload(self) -> dict:
        """Manually reload."""
        return self._post("/reload")

    # === Status ===

    def get_status(self) -> dict:
        """Get complete game status."""
        return self._get("/status")

    def get_turret_status(self) -> dict:
        """Get turret status only."""
        return self._get("/status")

    def get_target(self) -> dict:
        """
        Get target through monocular/scope view.
        Returns target visibility and angular offsets if visible in scope FOV.
        """
        return self._get("/target")

    def get_target_radar(self) -> dict:
        """
        Get full target info (debug/radar mode).
        Returns position, velocity, bearing, elevation, range.
        """
        return self._get("/target/radar")

    def get_game(self) -> dict:
        """Get full game status including target, turret, weather, stats."""
        return self._get("/game")

    def get_weather(self) -> dict:
        """Get current weather conditions."""
        return self._get("/weather")

    # === WebSocket Events ===

    def on_event(self, callback: Callable[[dict], None]):
        """
        Subscribe to real-time events via WebSocket.
        
        Events:
        - shot_fired
        - target_hit
        - target_escaped
        - overheated / cooled_down
        - reloaded
        - round_start / round_end
        """
        self._event_callback = callback
        if not self._ws_running:
            self._start_ws_listener()

    def _start_ws_listener(self):
        """Start WebSocket listener in background thread."""
        import asyncio
        import websockets

        self._ws_running = True

        def ws_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._ws_loop())

        self._event_thread = threading.Thread(
            target=ws_thread, daemon=True, name="ws-client"
        )
        self._event_thread.start()

    async def _ws_loop(self):
        import websockets
        while self._ws_running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    async for message in ws:
                        try:
                            event = json.loads(message)
                            if self._event_callback:
                                self._event_callback(event)
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                await __import__('asyncio').sleep(1)

    # === Utilities ===

    def wait_on_target(self, timeout: float = 5.0) -> bool:
        """Wait until turret has reached its target orientation."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_turret_status()
            if status.get("on_target"):
                return True
            time.sleep(0.05)
        return False

    def burst(self, duration: float = 0.5):
        """Fire a burst for given duration."""
        self.fire(True)
        time.sleep(duration)
        self.fire(False)

    def close(self):
        """Clean up."""
        self._ws_running = False
        self._http.close()

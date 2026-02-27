"""
WebSocket Event Server

Pushes real-time events to connected clients:
  - round_fired: when a round is fired
  - target_hit: when target is destroyed
  - target_escaped: when target leaves zone
  - overheat: barrel overheated
  - reload_start / reload_complete
  - round_start / round_end
  - weather_update
"""

import json
import asyncio
import threading
import logging
from typing import Set

logger = logging.getLogger("turret_ws")


class EventBroadcaster:
    """
    Simple event broadcaster that works without asyncio in the main thread.
    Queues events and sends them via WebSocket in a background thread.
    """
    
    def __init__(self, host="127.0.0.1", port=8421):
        self.host = host
        self.port = port
        self._event_queue = []
        self._lock = threading.Lock()
        self._clients: Set = set()
        self._thread = None
        self._running = False
        self._loop = None
    
    def start(self):
        """Start WebSocket server in background thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="turret_ws"
        )
        self._thread.start()
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
    
    def stop(self):
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
    
    def push_event(self, event: dict):
        """Queue a game event for broadcast (compat with app.py)."""
        event_type = event.get("type", "unknown")
        self.broadcast(event_type, event)

    def broadcast(self, event_type: str, data: dict = None):
        """Queue an event for broadcast (thread-safe)."""
        event = {
            "event": event_type,
            "data": data or {},
        }
        with self._lock:
            self._event_queue.append(json.dumps(event))
        
        # Schedule send in async loop
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._flush_queue())
            )
    
    async def _flush_queue(self):
        """Send queued events to all clients."""
        with self._lock:
            messages = self._event_queue.copy()
            self._event_queue.clear()
        
        if not messages or not self._clients:
            return
        
        disconnected = set()
        for client in self._clients:
            for msg in messages:
                try:
                    await client.send(msg)
                except Exception:
                    disconnected.add(client)
        
        self._clients -= disconnected
    
    def _run_server(self):
        """Run async WebSocket server."""
        try:
            import websockets
            
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            async def handler(websocket, path=None):
                self._clients.add(websocket)
                logger.info(f"WS client connected ({len(self._clients)} total)")
                try:
                    # Send welcome
                    await websocket.send(json.dumps({
                        "event": "connected",
                        "data": {"message": "Turret Simulator WebSocket"}
                    }))
                    # Keep connection alive
                    async for message in websocket:
                        pass  # We don't expect client messages
                except Exception:
                    pass
                finally:
                    self._clients.discard(websocket)
                    logger.info(f"WS client disconnected ({len(self._clients)} total)")
            
            start_server = websockets.serve(
                handler, self.host, self.port
            )
            
            self._loop.run_until_complete(start_server)
            self._loop.run_forever()
        except ImportError:
            logger.warning("websockets package not available, WS server disabled")
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")

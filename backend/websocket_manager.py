from typing import List
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket Client connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket Client disconnected. Remaining: {len(self.active_connections)}")

    def broadcast(self, message: dict):
        """Thread-safe broadcast for use in background tasks"""
        import asyncio
        import concurrent.futures

        logger.debug(f"Broadcasting event '{message.get('event', 'unknown')}' to {len(self.active_connections)} connections")

        # We need the main event loop that's running the WebSocket connections
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no loop in this thread, we need to find the main one
            # But in FastAPI, we can usually get the running loop
            logger.warning("No event loop found, cannot broadcast")
            return 

        async def _send_to_all():
            sent_count = 0
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send to connection: {e}")
            if sent_count > 0:
                logger.debug(f"Successfully sent to {sent_count} clients")

        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_send_to_all(), loop)
        else:
            # Fallback for start-up/shut-down
            logger.warning("Event loop not running, broadcasting synchronously")
            asyncio.run(_send_to_all())

manager = ConnectionManager()

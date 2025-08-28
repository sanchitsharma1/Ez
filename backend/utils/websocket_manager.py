import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time communication"""
    
    def __init__(self):
        # Active connections by client_id
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Message queues for offline clients
        self.message_queues: Dict[str, list] = {}
        
        # Broadcast channels
        self.broadcast_channels: Dict[str, Set[str]] = {}
        
        # Connection stats
        self.connection_count = 0
        self.total_messages = 0
    
    async def connect(self, websocket: WebSocket, client_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Accept a new WebSocket connection"""
        try:
            await websocket.accept()
            
            # Store connection
            self.active_connections[client_id] = websocket
            self.connection_metadata[client_id] = {
                "connected_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "message_count": 0,
                **(metadata or {})
            }
            
            self.connection_count += 1
            
            # Deliver queued messages
            await self._deliver_queued_messages(client_id)
            
            logger.info(f"Client {client_id} connected. Total connections: {self.connection_count}")
            
            # Send connection confirmation
            await self.send_message(client_id, {
                "type": "connection_established",
                "client_id": client_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error connecting client {client_id}: {e}")
            await self.disconnect(client_id)
    
    async def disconnect(self, client_id: str):
        """Remove a WebSocket connection"""
        try:
            if client_id in self.active_connections:
                # Close connection if still open
                websocket = self.active_connections[client_id]
                try:
                    await websocket.close()
                except Exception:
                    pass  # Connection might already be closed
                
                # Clean up connection data
                del self.active_connections[client_id]
                if client_id in self.connection_metadata:
                    del self.connection_metadata[client_id]
                
                # Remove from broadcast channels
                for channel_clients in self.broadcast_channels.values():
                    channel_clients.discard(client_id)
                
                self.connection_count -= 1
                
                logger.info(f"Client {client_id} disconnected. Total connections: {self.connection_count}")
        
        except Exception as e:
            logger.error(f"Error disconnecting client {client_id}: {e}")
    
    async def send_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific client"""
        try:
            if client_id in self.active_connections:
                websocket = self.active_connections[client_id]
                
                # Add timestamp if not present
                if "timestamp" not in message:
                    message["timestamp"] = datetime.utcnow().isoformat()
                
                await websocket.send_text(json.dumps(message))
                
                # Update connection metadata
                if client_id in self.connection_metadata:
                    self.connection_metadata[client_id]["last_activity"] = datetime.utcnow()
                    self.connection_metadata[client_id]["message_count"] += 1
                
                self.total_messages += 1
                return True
            else:
                # Queue message for offline client
                await self._queue_message(client_id, message)
                return False
                
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected during send")
            await self.disconnect(client_id)
            return False
        except Exception as e:
            logger.error(f"Error sending message to {client_id}: {e}")
            await self.disconnect(client_id)
            return False
    
    async def send_error(self, client_id: str, error_message: str, error_code: Optional[str] = None):
        """Send error message to client"""
        error_msg = {
            "type": "error",
            "error": error_message,
            "error_code": error_code,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_message(client_id, error_msg)
    
    async def send_typing_indicator(self, client_id: str, is_typing: bool, agent_id: Optional[str] = None):
        """Send typing indicator"""
        typing_msg = {
            "type": "typing_start" if is_typing else "typing_end",
            "agent_id": agent_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_message(client_id, typing_msg)
    
    async def broadcast_message(self, message: Dict[str, Any], exclude_client: Optional[str] = None):
        """Broadcast message to all connected clients"""
        disconnected_clients = []
        
        for client_id in list(self.active_connections.keys()):
            if client_id != exclude_client:
                success = await self.send_message(client_id, message)
                if not success:
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
    
    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any], exclude_client: Optional[str] = None):
        """Broadcast message to specific channel"""
        if channel not in self.broadcast_channels:
            return
        
        disconnected_clients = []
        
        for client_id in list(self.broadcast_channels[channel]):
            if client_id != exclude_client:
                success = await self.send_message(client_id, message)
                if not success:
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
    
    async def join_channel(self, client_id: str, channel: str):
        """Add client to broadcast channel"""
        if channel not in self.broadcast_channels:
            self.broadcast_channels[channel] = set()
        
        self.broadcast_channels[channel].add(client_id)
        logger.info(f"Client {client_id} joined channel {channel}")
    
    async def leave_channel(self, client_id: str, channel: str):
        """Remove client from broadcast channel"""
        if channel in self.broadcast_channels:
            self.broadcast_channels[channel].discard(client_id)
            
            # Remove empty channels
            if not self.broadcast_channels[channel]:
                del self.broadcast_channels[channel]
        
        logger.info(f"Client {client_id} left channel {channel}")
    
    async def _queue_message(self, client_id: str, message: Dict[str, Any]):
        """Queue message for offline client"""
        if client_id not in self.message_queues:
            self.message_queues[client_id] = []
        
        # Add expiry time to message
        message["queued_at"] = datetime.utcnow().isoformat()
        message["expires_at"] = (datetime.utcnow().timestamp() + 3600)  # 1 hour expiry
        
        self.message_queues[client_id].append(message)
        
        # Keep only last 50 messages per client
        if len(self.message_queues[client_id]) > 50:
            self.message_queues[client_id] = self.message_queues[client_id][-50:]
        
        logger.debug(f"Queued message for offline client {client_id}")
    
    async def _deliver_queued_messages(self, client_id: str):
        """Deliver queued messages to reconnected client"""
        if client_id not in self.message_queues:
            return
        
        current_time = datetime.utcnow().timestamp()
        valid_messages = []
        
        # Filter out expired messages
        for message in self.message_queues[client_id]:
            expires_at = message.get("expires_at", current_time + 1)
            if expires_at > current_time:
                # Remove queuing metadata
                message.pop("queued_at", None)
                message.pop("expires_at", None)
                valid_messages.append(message)
        
        # Send valid messages
        for message in valid_messages:
            await self.send_message(client_id, message)
        
        # Clear message queue
        del self.message_queues[client_id]
        
        if valid_messages:
            logger.info(f"Delivered {len(valid_messages)} queued messages to {client_id}")
    
    async def send_stream_chunk(self, client_id: str, content: str, agent_id: str, session_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Send streaming content chunk"""
        chunk_message = {
            "type": "stream_chunk",
            "content": content,
            "agent_id": agent_id,
            "session_id": session_id,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_message(client_id, chunk_message)
    
    async def send_stream_end(self, client_id: str, agent_id: str, session_id: str):
        """Send stream end marker"""
        end_message = {
            "type": "stream_end",
            "agent_id": agent_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_message(client_id, end_message)
    
    def is_connected(self, client_id: str) -> bool:
        """Check if client is connected"""
        return client_id in self.active_connections
    
    def get_connection_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get connection information"""
        return self.connection_metadata.get(client_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection manager statistics"""
        return {
            "active_connections": self.connection_count,
            "total_messages_sent": self.total_messages,
            "queued_messages": sum(len(queue) for queue in self.message_queues.values()),
            "broadcast_channels": len(self.broadcast_channels),
            "clients_with_queued_messages": len(self.message_queues)
        }
    
    async def ping_clients(self):
        """Send ping to all connected clients"""
        ping_message = {
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast_message(ping_message)
    
    async def cleanup_expired_queues(self):
        """Clean up expired message queues"""
        current_time = datetime.utcnow().timestamp()
        clients_to_clean = []
        
        for client_id, messages in self.message_queues.items():
            valid_messages = [
                msg for msg in messages 
                if msg.get("expires_at", current_time + 1) > current_time
            ]
            
            if valid_messages:
                self.message_queues[client_id] = valid_messages
            else:
                clients_to_clean.append(client_id)
        
        # Remove empty queues
        for client_id in clients_to_clean:
            del self.message_queues[client_id]
        
        if clients_to_clean:
            logger.info(f"Cleaned up expired message queues for {len(clients_to_clean)} clients")

class WebSocketManager:
    """Enhanced WebSocket manager with additional features"""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.cleanup_task: Optional[asyncio.Task] = None
        self.ping_task: Optional[asyncio.Task] = None
    
    async def start_background_tasks(self):
        """Start background maintenance tasks"""
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.ping_task = asyncio.create_task(self._ping_loop())
        logger.info("WebSocket background tasks started")
    
    async def stop_background_tasks(self):
        """Stop background maintenance tasks"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.ping_task:
            self.ping_task.cancel()
        logger.info("WebSocket background tasks stopped")
    
    async def _cleanup_loop(self):
        """Background task for cleaning up expired data"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                await self.connection_manager.cleanup_expired_queues()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket cleanup loop: {e}")
    
    async def _ping_loop(self):
        """Background task for pinging clients"""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                await self.connection_manager.ping_clients()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket ping loop: {e}")
    
    @asynccontextmanager
    async def websocket_connection(self, websocket: WebSocket, client_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for WebSocket connections"""
        try:
            await self.connection_manager.connect(websocket, client_id, metadata)
            yield self.connection_manager
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for client {client_id}")
        except Exception as e:
            logger.error(f"WebSocket error for client {client_id}: {e}")
        finally:
            await self.connection_manager.disconnect(client_id)
    
    def get_manager(self) -> ConnectionManager:
        """Get the connection manager instance"""
        return self.connection_manager

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

async def get_websocket_manager() -> WebSocketManager:
    """FastAPI dependency for WebSocket manager"""
    return websocket_manager
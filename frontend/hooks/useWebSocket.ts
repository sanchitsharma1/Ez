import { useEffect, useRef, useCallback } from 'react';
import { useChatStore } from '@/stores/chatStore';

interface WebSocketMessage {
  type: string;
  content: string;
  agent_id: string;
  session_id: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000; // 1 second

  const {
    addMessage,
    setTyping,
    setConnected,
    sessionId,
  } = useChatStore();

  const getWebSocketURL = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = process.env.NODE_ENV === 'production' 
      ? window.location.host 
      : 'localhost:8000';
    return `${protocol}//${host}/ws/chat/${sessionId}`;
  }, [sessionId]);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data: WebSocketMessage = JSON.parse(event.data);
      
      switch (data.type) {
        case 'text':
          // Add assistant message
          addMessage({
            content: data.content,
            role: 'assistant',
            agentId: data.agent_id,
            metadata: data.metadata,
          });
          break;
          
        case 'typing_start':
          setTyping(true);
          break;
          
        case 'typing_end':
          setTyping(false);
          break;
          
        case 'voice':
          // Handle voice response
          if (data.metadata?.audio_url) {
            playAudio(data.metadata.audio_url);
          }
          break;
          
        case 'error':
          console.error('WebSocket error:', data.content);
          addMessage({
            content: data.content,
            role: 'assistant',
            agentId: 'carol',
            metadata: { error: true },
          });
          break;
          
        case 'system':
          // Handle system messages (e.g., approval notifications)
          if (data.metadata?.approval_required) {
            // Show approval notification
            showApprovalNotification(data.metadata);
          }
          break;
          
        default:
          console.log('Unknown message type:', data.type);
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }, [addMessage, setTyping]);

  const handleOpen = useCallback(() => {
    console.log('WebSocket connected');
    setConnected(true);
    reconnectAttempts.current = 0;
    
    // Clear any pending reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, [setConnected]);

  const handleClose = useCallback(() => {
    console.log('WebSocket disconnected');
    setConnected(false);
    wsRef.current = null;
    
    // Attempt to reconnect if we haven't exceeded max attempts
    if (reconnectAttempts.current < maxReconnectAttempts) {
      const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts.current);
      console.log(`Attempting to reconnect in ${delay}ms (attempt ${reconnectAttempts.current + 1})`);
      
      reconnectTimeoutRef.current = setTimeout(() => {
        reconnectAttempts.current++;
        connect();
      }, delay);
    } else {
      console.error('Max reconnection attempts reached');
    }
  }, [setConnected]);

  const handleError = useCallback((error: Event) => {
    console.error('WebSocket error:', error);
    setConnected(false);
  }, [setConnected]);

  const connect = useCallback(() => {
    if (!sessionId) {
      console.warn('Cannot connect WebSocket: no session ID');
      return;
    }

    // Close existing connection if any
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    try {
      const wsURL = getWebSocketURL();
      console.log('Connecting to WebSocket:', wsURL);
      
      wsRef.current = new WebSocket(wsURL);
      wsRef.current.onopen = handleOpen;
      wsRef.current.onmessage = handleMessage;
      wsRef.current.onclose = handleClose;
      wsRef.current.onerror = handleError;
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      setConnected(false);
    }
  }, [sessionId, getWebSocketURL, handleOpen, handleMessage, handleClose, handleError, setConnected]);

  const disconnect = useCallback(() => {
    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close WebSocket connection
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnect');
      wsRef.current = null;
    }
    
    setConnected(false);
    reconnectAttempts.current = 0;
  }, [setConnected]);

  const sendWebSocketMessage = useCallback((data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(data));
        return true;
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
        return false;
      }
    } else {
      console.warn('WebSocket not connected, cannot send message');
      return false;
    }
  }, []);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connect,
    disconnect,
    sendWebSocketMessage,
  };
}

// Helper function to play audio responses
function playAudio(audioUrl: string) {
  const audio = new Audio(audioUrl);
  audio.play().catch(error => {
    console.error('Error playing audio:', error);
  });
}

// Helper function to show approval notifications
function showApprovalNotification(metadata: Record<string, any>) {
  // This would integrate with a notification system
  console.log('Approval required:', metadata);
  
  // You could use a toast notification library here
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('Approval Required', {
      body: metadata.approval_description || 'An action requires your approval',
      icon: '/icon-192x192.png',
    });
  }
}
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  agentId: string;
  timestamp: Date;
  metadata?: Record<string, any>;
}

interface ChatState {
  messages: Message[];
  isTyping: boolean;
  isConnected: boolean;
  sessionId: string;
  currentAgent: string | null;
  mode: 'online' | 'offline';
  voiceEnabled: boolean;
  
  // Actions
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  removeMessage: (id: string) => void;
  clearMessages: () => void;
  setTyping: (isTyping: boolean) => void;
  setConnected: (isConnected: boolean) => void;
  setSessionId: (sessionId: string) => void;
  setCurrentAgent: (agentId: string | null) => void;
  setMode: (mode: 'online' | 'offline') => void;
  setVoiceEnabled: (enabled: boolean) => void;
  sendMessage: (data: {
    message: string;
    agent_id?: string;
    mode?: 'online' | 'offline';
    voice_enabled?: boolean;
    session_id?: string;
  }) => Promise<void>;
}

export const useChatStore = create<ChatState>()(
  devtools(
    persist(
      (set, get) => ({
        messages: [],
        isTyping: false,
        isConnected: false,
        sessionId: '',
        currentAgent: null,
        mode: 'online',
        voiceEnabled: false,

        addMessage: (message) => {
          const newMessage: Message = {
            ...message,
            id: crypto.randomUUID(),
            timestamp: new Date(),
          };
          
          set((state) => ({
            messages: [...state.messages, newMessage],
          }));
        },

        updateMessage: (id, updates) => {
          set((state) => ({
            messages: state.messages.map(msg => 
              msg.id === id ? { ...msg, ...updates } : msg
            ),
          }));
        },

        removeMessage: (id) => {
          set((state) => ({
            messages: state.messages.filter(msg => msg.id !== id),
          }));
        },

        clearMessages: () => {
          set({ messages: [] });
        },

        setTyping: (isTyping) => {
          set({ isTyping });
        },

        setConnected: (isConnected) => {
          set({ isConnected });
        },

        setSessionId: (sessionId) => {
          set({ sessionId });
          // Store in sessionStorage for backend reference
          if (typeof window !== 'undefined') {
            sessionStorage.setItem('session_id', sessionId);
          }
        },

        setCurrentAgent: (agentId) => {
          set({ currentAgent: agentId });
        },

        setMode: (mode) => {
          set({ mode });
        },

        setVoiceEnabled: (enabled) => {
          set({ voiceEnabled: enabled });
        },

        sendMessage: async (data) => {
          const { addMessage, setTyping } = get();
          
          console.log('Sending message:', data);
          
          // Add user message
          addMessage({
            content: data.message,
            role: 'user',
            agentId: 'user',
          });

          // Set typing indicator
          setTyping(true);

          try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const authToken = getAuthToken();
            const headers: Record<string, string> = {
              'Content-Type': 'application/json',
            };
            
            // Only add Authorization header if token exists
            if (authToken) {
              headers['Authorization'] = `Bearer ${authToken}`;
            }
            
            console.log('Making request to:', `${apiUrl}/api/chat`);
            
            const response = await fetch(`${apiUrl}/api/chat`, {
              method: 'POST',
              headers,
              body: JSON.stringify({
                message: data.message,
                agent_id: data.agent_id,
                session_id: data.session_id || get().sessionId,
                mode: data.mode || get().mode,
                voice_enabled: data.voice_enabled || get().voiceEnabled,
              }),
            });

            console.log('Response status:', response.status);
            console.log('Response ok:', response.ok);

            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('Response data:', result);

            // Add assistant response
            addMessage({
              content: result.message,
              role: 'assistant',
              agentId: result.agent_id,
              metadata: result.metadata,
            });

            // Update session ID if provided
            if (result.session_id && result.session_id !== get().sessionId) {
              get().setSessionId(result.session_id);
            }

          } catch (error) {
            console.error('Error sending message:', error);
            
            // Add error message
            addMessage({
              content: 'I apologize, but I encountered an error while processing your request. Please try again.',
              role: 'assistant',
              agentId: 'carol',
              metadata: { error: true },
            });
          } finally {
            setTyping(false);
          }
        },
      }),
      {
        name: 'chat-store',
        partialize: (state) => ({
          sessionId: state.sessionId,
          mode: state.mode,
          voiceEnabled: state.voiceEnabled,
          // Don't persist messages for privacy
        }),
      }
    ),
    { name: 'chat-store' }
  )
);

// Helper function to get auth token
function getAuthToken(): string {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('auth_token') || '';
  }
  return '';
}

// Initialize session ID if not exists
if (typeof window !== 'undefined') {
  const store = useChatStore.getState();
  if (!store.sessionId) {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2)}`;
    store.setSessionId(newSessionId);
  }
}
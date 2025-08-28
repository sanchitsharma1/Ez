import { storage } from './utils'

interface ApiConfig {
  baseURL: string
  timeout: number
  headers: Record<string, string>
}

class ApiClient {
  private config: ApiConfig
  private baseURL: string

  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    this.config = {
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    }
  }

  private getAuthToken(): string | null {
    return storage.get('auth_token', null)
  }

  private getAuthHeaders(): Record<string, string> {
    const token = this.getAuthToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`
    const headers = {
      ...this.config.headers,
      ...this.getAuthHeaders(),
      ...options.headers,
    }

    const config: RequestInit = {
      ...options,
      headers,
    }

    // Add timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), this.config.timeout)
    config.signal = controller.signal

    try {
      const response = await fetch(url, config)
      clearTimeout(timeoutId)

      if (!response.ok) {
        if (response.status === 401) {
          // Token expired, redirect to login
          storage.remove('auth_token')
          window.location.href = '/auth/login'
          throw new Error('Authentication required')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      // Handle different content types
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        return await response.json()
      } else if (contentType && contentType.includes('text/')) {
        return (await response.text()) as unknown as T
      } else {
        return (await response.blob()) as unknown as T
      }
    } catch (error) {
      clearTimeout(timeoutId)
      throw error
    }
  }

  // HTTP Methods
  async get<T>(endpoint: string, params?: Record<string, any>): Promise<T> {
    let url = endpoint
    if (params) {
      const searchParams = new URLSearchParams()
      Object.entries(params).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          searchParams.append(key, String(value))
        }
      })
      url += `?${searchParams.toString()}`
    }

    return this.request<T>(url, { method: 'GET' })
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async put<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async patch<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }

  // File upload
  async upload<T>(endpoint: string, file: File, additionalData?: Record<string, any>): Promise<T> {
    const formData = new FormData()
    formData.append('file', file)
    
    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        formData.append(key, String(value))
      })
    }

    return this.request<T>(endpoint, {
      method: 'POST',
      body: formData,
      headers: {
        // Remove Content-Type to let browser set it with boundary
        ...this.getAuthHeaders(),
      },
    })
  }

  // Streaming requests
  async stream(endpoint: string, data?: any): Promise<ReadableStream> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'POST',
      headers: {
        ...this.config.headers,
        ...this.getAuthHeaders(),
      },
      body: data ? JSON.stringify(data) : undefined,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    return response.body!
  }

  // WebSocket connection
  createWebSocket(endpoint: string): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${endpoint}`
    return new WebSocket(wsUrl)
  }
}

// API client instance
export const api = new ApiClient()

// Typed API methods
export const authApi = {
  login: (credentials: { username: string; password: string }) =>
    api.post<{ access_token: string; user: any }>('/auth/login', credentials),
  
  register: (userData: { username: string; email: string; password: string; full_name?: string }) =>
    api.post<{ user: any }>('/auth/register', userData),
  
  logout: () => api.post<{ message: string }>('/auth/logout'),
  
  me: () => api.get<any>('/auth/me'),
  
  refreshToken: () => api.post<{ access_token: string }>('/auth/refresh-token'),
}

export const chatApi = {
  sendMessage: (data: { message: string; agent_id?: string; mode?: string }) =>
    api.post<{ message: string; agent_id: string; session_id: string }>('/api/chat', data),
  
  streamMessage: (data: { message: string; agent_id?: string; mode?: string }) =>
    api.stream('/api/chat/stream', data),
}

export const agentsApi = {
  list: () => api.get<any[]>('/api/agents'),
  
  get: (agentId: string) => api.get<any>(`/api/agents/${agentId}`),
  
  update: (agentId: string, config: any) =>
    api.put<any>(`/api/agents/${agentId}`, config),
  
  getStatus: () => api.get<Record<string, any>>('/api/agents/status'),
}

export const memoryApi = {
  search: (query: { query: string; limit?: number; agent_id?: string }) =>
    api.post<{ memories: any[]; total: number }>('/api/memory/search', query),
  
  create: (memory: { content: string; content_type?: string; tags?: string[] }) =>
    api.post<{ id: string }>('/api/memory', memory),
  
  list: (params?: { limit?: number; offset?: number; agent_id?: string }) =>
    api.get<any[]>('/api/memory', params),
  
  delete: (memoryId: string) => api.delete(`/api/memory/${memoryId}`),
}

export const tasksApi = {
  list: (params?: { status?: string; limit?: number; offset?: number }) =>
    api.get<any[]>('/api/tasks', params),
  
  create: (task: { title: string; description?: string; priority?: number; due_date?: string }) =>
    api.post<any>('/api/tasks', task),
  
  update: (taskId: string, updates: { title?: string; description?: string; status?: string; priority?: number }) =>
    api.put<any>(`/api/tasks/${taskId}`, updates),
  
  delete: (taskId: string) => api.delete(`/api/tasks/${taskId}`),
  
  complete: (taskId: string) => api.patch<any>(`/api/tasks/${taskId}/complete`, {}),
}

export const calendarApi = {
  listEvents: (params?: { start_date?: string; end_date?: string; limit?: number }) =>
    api.get<any[]>('/api/calendar/events', params),
  
  createEvent: (event: { 
    title: string; 
    description?: string; 
    start_time: string; 
    end_time: string; 
    location?: string;
    attendees?: string[];
  }) => api.post<any>('/api/calendar/events', event),
  
  updateEvent: (eventId: string, updates: any) =>
    api.put<any>(`/api/calendar/events/${eventId}`, updates),
  
  deleteEvent: (eventId: string) => api.delete(`/api/calendar/events/${eventId}`),
  
  syncWithGoogle: () => api.post<{ message: string }>('/api/calendar/sync/google', {}),
  
  exportICS: (params?: { start_date?: string; end_date?: string }) =>
    api.get<Blob>('/api/calendar/export/ics', params),
}

export const emailApi = {
  listEmails: (params?: { limit?: number; offset?: number; folder?: string }) =>
    api.get<any[]>('/api/email/messages', params),
  
  sendEmail: (email: {
    to: string[];
    cc?: string[];
    bcc?: string[];
    subject: string;
    body: string;
    html_body?: string;
    attachments?: string[];
  }) => api.post<{ message_id: string }>('/api/email/send', email),
  
  replyToEmail: (messageId: string, reply: { body: string; html_body?: string }) =>
    api.post<{ message_id: string }>(`/api/email/messages/${messageId}/reply`, reply),
  
  getEmailContent: (messageId: string) =>
    api.get<any>(`/api/email/messages/${messageId}`),
  
  searchEmails: (query: string) =>
    api.get<any[]>('/api/email/search', { q: query }),
  
  connectGmail: () => api.get<{ auth_url: string }>('/api/email/connect/gmail'),
  
  connectZoho: () => api.get<{ auth_url: string }>('/api/email/connect/zoho'),
  
  disconnectEmail: (provider: 'gmail' | 'zoho') =>
    api.delete(`/api/email/disconnect/${provider}`),
}

export const voiceApi = {
  transcribe: (audioData: string, format: string = 'wav') =>
    api.post<{ text: string; confidence: number }>('/api/voice/transcribe', { 
      audio_data: audioData, 
      format 
    }),
  
  synthesize: (text: string, agentId: string, voiceSettings?: any) =>
    api.post<{ audio_url: string; duration: number }>('/api/voice/synthesize', {
      text,
      agent_id: agentId,
      voice_settings: voiceSettings
    }),
}

export const systemApi = {
  getStatus: () => api.get<any>('/api/system/status'),
  
  getMetrics: () => api.get<any>('/api/system/metrics'),
  
  getProcesses: (sortBy?: string) =>
    api.get<any[]>('/api/system/processes', { sort_by: sortBy }),
  
  executeCommand: (command: string, commandType: string) =>
    api.post<{ success: boolean; output?: string; error?: string }>('/api/system/execute', {
      command,
      command_type: commandType
    }),
  
  getHealthReport: () => api.get<any>('/api/system/health'),
}

export const fileApi = {
  upload: (file: File, metadata?: any) =>
    api.upload<{ file_id: string; filename: string; file_path: string }>('/api/files/upload', file, metadata),
  
  extractText: (fileId: string) =>
    api.post<{ text: string; metadata: any }>(`/api/files/${fileId}/extract`, {}),
  
  delete: (fileId: string) => api.delete(`/api/files/${fileId}`),
  
  list: (params?: { category?: string; limit?: number; offset?: number }) =>
    api.get<any[]>('/api/files', params),
  
  getInfo: (fileId: string) => api.get<any>(`/api/files/${fileId}/info`),
}

export const knowledgeApi = {
  search: (query: string, params?: { limit?: number; content_types?: string[]; tags?: string[] }) =>
    api.post<{ results: any[]; total: number }>('/api/knowledge/search', { query, ...params }),
  
  create: (entry: { 
    title: string; 
    content: string; 
    content_type?: string; 
    tags?: string[]; 
    source_file?: string; 
  }) => api.post<{ id: string }>('/api/knowledge', entry),
  
  update: (entryId: string, updates: any) =>
    api.put<any>(`/api/knowledge/${entryId}`, updates),
  
  delete: (entryId: string) => api.delete(`/api/knowledge/${entryId}`),
  
  list: (params?: { limit?: number; offset?: number; content_type?: string; order_by?: string }) =>
    api.get<any[]>('/api/knowledge', params),
  
  getStats: () => api.get<any>('/api/knowledge/stats'),
}

export const approvalsApi = {
  listPending: () => api.get<any[]>('/api/approvals/pending'),
  
  respond: (approvalId: string, response: { decision: 'approved' | 'rejected'; reason?: string }) =>
    api.post<{ message: string }>(`/api/approvals/${approvalId}/respond`, response),
  
  getHistory: (params?: { limit?: number; offset?: number }) =>
    api.get<any[]>('/api/approvals/history', params),
}

export const whatsappApi = {
  sendMessage: (to: string, message: string, messageType?: 'text' | 'image' | 'document') =>
    api.post<{ message_id: string }>('/api/whatsapp/send', {
      to,
      message,
      message_type: messageType || 'text'
    }),
  
  getMessages: (params?: { limit?: number; offset?: number }) =>
    api.get<any[]>('/api/whatsapp/messages', params),
  
  getStatus: () => api.get<{ connected: boolean; phone_number: string }>('/api/whatsapp/status'),
  
  connect: () => api.post<{ qr_code?: string; status: string }>('/api/whatsapp/connect', {}),
  
  disconnect: () => api.post<{ message: string }>('/api/whatsapp/disconnect', {}),
}

export const modelsApi = {
  listOnline: () => api.get<string[]>('/api/models/online'),
  
  listOffline: () => api.get<string[]>('/api/models/offline'),
  
  downloadModel: (modelName: string) =>
    api.post<{ message: string; status: string }>('/api/models/download', { model_name: modelName }),
  
  deleteModel: (modelName: string) =>
    api.delete(`/api/models/offline/${modelName}`),
  
  getModelInfo: (modelName: string, mode: 'online' | 'offline') =>
    api.get<any>(`/api/models/${mode}/${modelName}/info`),
}

export const settingsApi = {
  getUserSettings: () => api.get<any>('/api/settings/user'),
  
  updateUserSettings: (settings: any) =>
    api.put<any>('/api/settings/user', settings),
  
  getAgentSettings: (agentId: string) =>
    api.get<any>(`/api/settings/agents/${agentId}`),
  
  updateAgentSettings: (agentId: string, settings: any) =>
    api.put<any>(`/api/settings/agents/${agentId}`, settings),
  
  getSystemSettings: () => api.get<any>('/api/settings/system'),
  
  updateSystemSettings: (settings: any) =>
    api.put<any>('/api/settings/system', settings),
  
  resetToDefaults: (category: 'user' | 'agents' | 'system') =>
    api.post<{ message: string }>('/api/settings/reset', { category }),
}

// Utility functions
export const handleApiError = (error: any) => {
  if (error.message === 'Authentication required') {
    // Already handled in the request method
    return
  }
  
  console.error('API Error:', error)
  
  // You can add more sophisticated error handling here
  if (error.message.includes('Network')) {
    throw new Error('Network connection failed. Please check your internet connection.')
  } else if (error.message.includes('500')) {
    throw new Error('Server error. Please try again later.')
  } else {
    throw error
  }
}

// Type definitions for common API responses
export interface User {
  id: string
  username: string
  email: string
  full_name?: string
  is_active: boolean
  is_admin: boolean
  created_at: string
  updated_at: string
}

export interface Agent {
  id: string
  name: string
  nickname?: string
  description?: string
  persona?: string
  capabilities: Array<{
    name: string
    description: string
    enabled: boolean
  }>
  voice_id?: string
  is_active: boolean
  config?: any
}

export interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  agentId: string
  timestamp: string
  metadata?: any
}
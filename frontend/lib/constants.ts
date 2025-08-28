export const AGENTS = {
  CAROL: {
    id: 'carol',
    name: 'Carol',
    description: 'Task Management & Productivity Assistant',
    color: 'blue',
    avatar: '/avatars/carol.png',
    capabilities: [
      'Task Management',
      'Project Planning',
      'Calendar Integration',
      'Productivity Coaching',
      'Deadline Tracking'
    ]
  },
  ALEX: {
    id: 'alex',
    name: 'Alex',
    description: 'Communications & Social Media Manager',
    color: 'green',
    avatar: '/avatars/alex.png',
    capabilities: [
      'Email Management',
      'Social Media',
      'WhatsApp Integration',
      'Communication Scheduling',
      'Contact Management'
    ]
  },
  SOFIA: {
    id: 'sofia',
    name: 'Sofia',
    description: 'Research & Analysis Specialist',
    color: 'purple',
    avatar: '/avatars/sofia.png',
    capabilities: [
      'Web Research',
      'Data Analysis',
      'Report Generation',
      'Information Synthesis',
      'Fact Checking'
    ]
  },
  MORGAN: {
    id: 'morgan',
    name: 'Morgan',
    description: 'Creative & Content Assistant',
    color: 'orange',
    avatar: '/avatars/morgan.png',
    capabilities: [
      'Creative Writing',
      'Content Creation',
      'Brainstorming',
      'Design Assistance',
      'Media Production'
    ]
  },
  JUDY: {
    id: 'judy',
    name: 'Judy',
    description: 'Executive & Decision Support',
    color: 'red',
    avatar: '/avatars/judy.png',
    capabilities: [
      'Executive Assistance',
      'Decision Making',
      'Risk Assessment',
      'Approval Workflows',
      'Strategic Planning'
    ]
  }
} as const

export const AGENT_IDS = Object.keys(AGENTS) as Array<keyof typeof AGENTS>

export const CONTENT_TYPES = {
  CONVERSATION: 'conversation',
  TASK: 'task',
  DOCUMENT: 'document',
  VOICE_TRANSCRIPTION: 'voice_transcription',
  APPROVAL: 'approval'
} as const

export const TASK_PRIORITIES = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  URGENT: 'urgent'
} as const

export const TASK_STATUSES = {
  PENDING: 'pending',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled'
} as const

export const APPROVAL_STATUSES = {
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  EXPIRED: 'expired'
} as const

export const MESSAGE_TYPES = {
  USER: 'user',
  AGENT: 'agent',
  SYSTEM: 'system'
} as const

export const SESSION_STATUSES = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  ARCHIVED: 'archived'
} as const

export const VOICE_SETTINGS = {
  MODELS: [
    { id: 'elevenlabs', name: 'ElevenLabs', type: 'cloud' },
    { id: 'coqui', name: 'Coqui TTS', type: 'local' },
    { id: 'azure', name: 'Azure Speech', type: 'cloud' }
  ],
  LANGUAGES: [
    { code: 'en-US', name: 'English (US)' },
    { code: 'en-GB', name: 'English (UK)' },
    { code: 'es-ES', name: 'Spanish' },
    { code: 'fr-FR', name: 'French' },
    { code: 'de-DE', name: 'German' },
    { code: 'it-IT', name: 'Italian' },
    { code: 'pt-BR', name: 'Portuguese (Brazil)' }
  ]
} as const

export const API_ENDPOINTS = {
  AUTH: {
    LOGIN: '/api/auth/login',
    REGISTER: '/api/auth/register',
    REFRESH: '/api/auth/refresh',
    LOGOUT: '/api/auth/logout'
  },
  AGENTS: {
    LIST: '/api/agents',
    GET: (id: string) => `/api/agents/${id}`,
    UPDATE: (id: string) => `/api/agents/${id}`,
    CHAT: (id: string) => `/api/agents/${id}/chat`,
    STATUS: (id: string) => `/api/agents/${id}/status`
  },
  TASKS: {
    LIST: '/api/tasks',
    CREATE: '/api/tasks',
    GET: (id: string) => `/api/tasks/${id}`,
    UPDATE: (id: string) => `/api/tasks/${id}`,
    DELETE: (id: string) => `/api/tasks/${id}`
  },
  MEMORY: {
    LIST: '/api/memory',
    SEARCH: '/api/memory/search',
    GET: (id: string) => `/api/memory/${id}`,
    DELETE: (id: string) => `/api/memory/${id}`,
    EXPORT: '/api/memory/export',
    STATS: '/api/memory/stats/summary'
  },
  CALENDAR: {
    EVENTS: '/api/calendar/events',
    SYNC: '/api/calendar/sync',
    EXPORT: '/api/calendar/export'
  },
  EMAIL: {
    MESSAGES: '/api/email/messages',
    SEND: '/api/email/send',
    SYNC: '/api/email/sync'
  },
  VOICE: {
    UPLOAD: '/api/voice/upload',
    PROCESS: '/api/voice/process',
    SYNTHESIZE: '/api/voice/synthesize',
    STREAM: '/api/voice/stream'
  },
  APPROVALS: {
    LIST: '/api/approvals',
    GET: (id: string) => `/api/approvals/${id}`,
    APPROVE: (id: string) => `/api/approvals/${id}/approve`,
    REJECT: (id: string) => `/api/approvals/${id}/reject`
  },
  SYSTEM: {
    HEALTH: '/api/system/health',
    STATUS: '/api/system/status',
    STATS: '/api/system/stats',
    LOGS: '/api/system/logs'
  }
} as const

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'access_token',
  REFRESH_TOKEN: 'refresh_token',
  USER_PREFERENCES: 'user_preferences',
  THEME: 'theme',
  SELECTED_AGENT: 'selected_agent',
  SIDEBAR_STATE: 'sidebar_state'
} as const

export const THEME_OPTIONS = {
  LIGHT: 'light',
  DARK: 'dark',
  SYSTEM: 'system'
} as const

export const DATE_FORMATS = {
  SHORT: 'MMM d',
  MEDIUM: 'MMM d, yyyy',
  LONG: 'MMMM d, yyyy',
  WITH_TIME: 'MMM d, yyyy h:mm a',
  TIME_ONLY: 'h:mm a',
  ISO: "yyyy-MM-dd'T'HH:mm:ss"
} as const

export const FILE_TYPES = {
  ALLOWED_EXTENSIONS: ['.txt', '.pdf', '.docx', '.md', '.json'],
  MAX_SIZE_MB: 10,
  MIME_TYPES: {
    TEXT: 'text/plain',
    PDF: 'application/pdf',
    DOCX: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    MARKDOWN: 'text/markdown',
    JSON: 'application/json'
  }
} as const

export const WEBSOCKET_EVENTS = {
  CONNECT: 'connect',
  DISCONNECT: 'disconnect',
  MESSAGE: 'message',
  AGENT_RESPONSE: 'agent_response',
  TASK_UPDATE: 'task_update',
  MEMORY_UPDATE: 'memory_update',
  SYSTEM_UPDATE: 'system_update',
  ERROR: 'error'
} as const

export const ERROR_MESSAGES = {
  NETWORK: 'Network error. Please check your connection.',
  UNAUTHORIZED: 'You are not authorized to access this resource.',
  FORBIDDEN: 'Access denied.',
  NOT_FOUND: 'The requested resource was not found.',
  SERVER_ERROR: 'An internal server error occurred.',
  VALIDATION_ERROR: 'Please check your input and try again.',
  FILE_TOO_LARGE: `File size exceeds ${FILE_TYPES.MAX_SIZE_MB}MB limit.`,
  INVALID_FILE_TYPE: `Only ${FILE_TYPES.ALLOWED_EXTENSIONS.join(', ')} files are allowed.`
} as const

export const SUCCESS_MESSAGES = {
  TASK_CREATED: 'Task created successfully',
  TASK_UPDATED: 'Task updated successfully',
  TASK_DELETED: 'Task deleted successfully',
  MEMORY_DELETED: 'Memory deleted successfully',
  FILE_UPLOADED: 'File uploaded successfully',
  SETTINGS_SAVED: 'Settings saved successfully',
  APPROVAL_PROCESSED: 'Approval processed successfully'
} as const

export const PAGINATION = {
  DEFAULT_LIMIT: 20,
  MAX_LIMIT: 100,
  DEFAULT_OFFSET: 0
} as const

export const RATE_LIMITS = {
  CHAT_MESSAGES_PER_MINUTE: 30,
  API_CALLS_PER_MINUTE: 60,
  FILE_UPLOADS_PER_HOUR: 10
} as const
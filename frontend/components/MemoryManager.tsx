"use client"

import React, { useState, useEffect } from 'react'
import { Search, Filter, Download, Trash2, Edit3, Eye, Calendar, User, Tag } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatTimeAgo, formatBytes } from '@/lib/utils'

interface Memory {
  id: string
  content: string
  content_type: string
  agent_id: string
  session_id: string
  tags: string[]
  metadata: Record<string, any>
  created_at: string
  updated_at: string
  similarity_score?: number
}

interface MemoryStats {
  total_memories: number
  memories_by_agent: Record<string, number>
  memories_by_type: Record<string, number>
  total_size_mb: number
  oldest_memory: string
  newest_memory: string
  top_tags: Array<{ tag: string; count: number }>
}

export default function MemoryManager() {
  const [memories, setMemories] = useState<Memory[]>([])
  const [stats, setStats] = useState<MemoryStats | null>(null)
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterAgent, setFilterAgent] = useState('all')
  const [filterType, setFilterType] = useState('all')
  const [sortBy, setSortBy] = useState('created_at')

  const agents = ['carol', 'alex', 'sofia', 'morgan', 'judy']
  const contentTypes = ['conversation', 'task', 'document', 'voice_transcription', 'approval']

  useEffect(() => {
    loadMemories()
    loadStats()
  }, [])

  const loadMemories = async () => {
    setIsLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterAgent !== 'all') params.append('agent_id', filterAgent)
      if (filterType !== 'all') params.append('content_type', filterType)
      params.append('limit', '100')

      const response = await fetch(`/api/memory?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setMemories(data)
      }
    } catch (error) {
      console.error('Error loading memories:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await fetch('/api/memory/stats/summary', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Error loading memory stats:', error)
    }
  }

  const searchMemories = async () => {
    if (!searchQuery.trim()) {
      loadMemories()
      return
    }

    setIsLoading(true)
    try {
      const response = await fetch('/api/memory/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          query: searchQuery,
          agent_id: filterAgent !== 'all' ? filterAgent : null,
          content_type: filterType !== 'all' ? filterType : null,
          limit: 100,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setMemories(data)
      }
    } catch (error) {
      console.error('Error searching memories:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const deleteMemory = async (memoryId: string) => {
    if (!confirm('Are you sure you want to delete this memory?')) return

    try {
      const response = await fetch(`/api/memory/${memoryId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        setMemories(memories.filter(m => m.id !== memoryId))
        setSelectedMemory(null)
        loadStats() // Refresh stats
      }
    } catch (error) {
      console.error('Error deleting memory:', error)
    }
  }

  const exportMemories = async (format: 'json' | 'csv') => {
    try {
      const params = new URLSearchParams({ format })
      if (filterAgent !== 'all') params.append('agent_id', filterAgent)
      if (filterType !== 'all') params.append('content_type', filterType)

      const response = await fetch(`/api/memory/export?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `memories_export.${format}`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (error) {
      console.error('Error exporting memories:', error)
    }
  }

  const filteredMemories = memories
    .filter(memory => 
      (filterAgent === 'all' || memory.agent_id === filterAgent) &&
      (filterType === 'all' || memory.content_type === filterType)
    )
    .sort((a, b) => {
      switch (sortBy) {
        case 'created_at':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        case 'similarity_score':
          return (b.similarity_score || 0) - (a.similarity_score || 0)
        case 'content_length':
          return b.content.length - a.content.length
        default:
          return 0
      }
    })

  return (
    <div className="flex h-full">
      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-2xl font-semibold">Memory Manager</h1>
            <div className="flex space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => exportMemories('json')}
              >
                <Download className="w-4 h-4 mr-2" />
                Export JSON
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => exportMemories('csv')}
              >
                <Download className="w-4 h-4 mr-2" />
                Export CSV
              </Button>
            </div>
          </div>

          {/* Search and Filters */}
          <div className="flex space-x-2 mb-4">
            <div className="flex-1 relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <Input
                placeholder="Search memories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && searchMemories()}
                className="pl-10"
              />
            </div>
            <Button onClick={searchMemories} disabled={isLoading}>
              Search
            </Button>
          </div>

          <div className="flex space-x-2">
            <Select
              value={filterAgent}
              onValueChange={setFilterAgent}
            >
              <option value="all">All Agents</option>
              {agents.map(agent => (
                <option key={agent} value={agent}>
                  {agent.charAt(0).toUpperCase() + agent.slice(1)}
                </option>
              ))}
            </Select>

            <Select
              value={filterType}
              onValueChange={setFilterType}
            >
              <option value="all">All Types</option>
              {contentTypes.map(type => (
                <option key={type} value={type}>
                  {type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </option>
              ))}
            </Select>

            <Select
              value={sortBy}
              onValueChange={setSortBy}
            >
              <option value="created_at">Date Created</option>
              <option value="similarity_score">Similarity</option>
              <option value="content_length">Content Length</option>
            </Select>
          </div>
        </div>

        {/* Stats Dashboard */}
        {stats && (
          <div className="p-4 bg-gray-50 border-b">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="font-semibold text-gray-600">Total Memories</div>
                <div className="text-xl font-bold">{stats.total_memories.toLocaleString()}</div>
              </div>
              <div>
                <div className="font-semibold text-gray-600">Total Size</div>
                <div className="text-xl font-bold">{stats.total_size_mb.toFixed(1)} MB</div>
              </div>
              <div>
                <div className="font-semibold text-gray-600">Top Agent</div>
                <div className="text-lg font-bold">
                  {Object.entries(stats.memories_by_agent)
                    .sort(([,a], [,b]) => b - a)[0]?.[0] || 'N/A'}
                </div>
              </div>
              <div>
                <div className="font-semibold text-gray-600">Top Type</div>
                <div className="text-lg font-bold">
                  {Object.entries(stats.memories_by_type)
                    .sort(([,a], [,b]) => b - a)[0]?.[0] || 'N/A'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Memory List */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex justify-center items-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : filteredMemories.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No memories found
            </div>
          ) : (
            <div className="divide-y">
              {filteredMemories.map((memory) => (
                <div
                  key={memory.id}
                  className="p-4 hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedMemory(memory)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {memory.agent_id}
                        </span>
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          {memory.content_type}
                        </span>
                        {memory.similarity_score && (
                          <span className="text-xs text-gray-500">
                            {Math.round(memory.similarity_score * 100)}% match
                          </span>
                        )}
                      </div>
                      
                      <p className="text-sm text-gray-900 line-clamp-2 mb-2">
                        {memory.content}
                      </p>
                      
                      <div className="flex items-center space-x-4 text-xs text-gray-500">
                        <span className="flex items-center">
                          <Calendar className="w-3 h-3 mr-1" />
                          {formatTimeAgo(memory.created_at)}
                        </span>
                        {memory.tags.length > 0 && (
                          <span className="flex items-center">
                            <Tag className="w-3 h-3 mr-1" />
                            {memory.tags.slice(0, 3).join(', ')}
                            {memory.tags.length > 3 && '...'}
                          </span>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-1 ml-4">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedMemory(memory)
                        }}
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteMemory(memory.id)
                        }}
                      >
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Memory Detail Panel */}
      {selectedMemory && (
        <div className="w-96 border-l bg-white">
          <div className="p-4 border-b">
            <div className="flex justify-between items-center">
              <h3 className="font-semibold">Memory Details</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedMemory(null)}
              >
                ×
              </Button>
            </div>
          </div>
          
          <div className="p-4 space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-600">Agent</label>
              <div className="mt-1">
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                  {selectedMemory.agent_id}
                </span>
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-600">Type</label>
              <div className="mt-1">
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
                  {selectedMemory.content_type}
                </span>
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-600">Content</label>
              <div className="mt-1 p-3 bg-gray-50 rounded-md text-sm">
                {selectedMemory.content}
              </div>
            </div>
            
            {selectedMemory.tags.length > 0 && (
              <div>
                <label className="text-sm font-medium text-gray-600">Tags</label>
                <div className="mt-1 flex flex-wrap gap-1">
                  {selectedMemory.tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            <div>
              <label className="text-sm font-medium text-gray-600">Created</label>
              <div className="mt-1 text-sm text-gray-900">
                {new Date(selectedMemory.created_at).toLocaleString()}
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-600">Session ID</label>
              <div className="mt-1 text-sm text-gray-900 font-mono">
                {selectedMemory.session_id}
              </div>
            </div>
            
            {Object.keys(selectedMemory.metadata).length > 0 && (
              <div>
                <label className="text-sm font-medium text-gray-600">Metadata</label>
                <div className="mt-1 p-3 bg-gray-50 rounded-md text-xs font-mono">
                  <pre>{JSON.stringify(selectedMemory.metadata, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
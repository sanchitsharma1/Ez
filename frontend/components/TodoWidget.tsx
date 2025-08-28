"use client"

import React, { useState, useEffect } from 'react'
import { Plus, Check, Clock, AlertCircle, Filter, Search, Calendar, User, Tag } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatDate, formatTimeAgo } from '@/lib/utils'

interface Task {
  id: string
  title: string
  description?: string
  status: 'pending' | 'in_progress' | 'completed'
  priority: 'low' | 'medium' | 'high'
  assigned_agent?: string
  due_date?: string
  tags: string[]
  metadata?: Record<string, any>
  created_at: string
  updated_at: string
  completed_at?: string
}

interface NewTaskForm {
  title: string
  description: string
  priority: 'low' | 'medium' | 'high'
  assigned_agent: string
  due_date: string
  tags: string
}

interface TaskStats {
  total_tasks: number
  tasks_by_status: Record<string, number>
  tasks_by_priority: Record<string, number>
  overdue_tasks: number
  due_today: number
  completion_rate: number
}

const INITIAL_FORM: NewTaskForm = {
  title: '',
  description: '',
  priority: 'medium',
  assigned_agent: '',
  due_date: '',
  tags: '',
}

export default function TodoWidget() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [showNewTaskDialog, setShowNewTaskDialog] = useState(false)
  const [newTaskForm, setNewTaskForm] = useState<NewTaskForm>(INITIAL_FORM)
  const [filter, setFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const agents = ['', 'carol', 'alex', 'sofia', 'morgan', 'judy']
  const priorities = ['low', 'medium', 'high']
  const statuses = ['pending', 'in_progress', 'completed']

  useEffect(() => {
    loadTasks()
    loadStats()
  }, [])

  const loadTasks = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/tasks', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setTasks(data)
      }
    } catch (error) {
      console.error('Error loading tasks:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await fetch('/api/tasks/stats/summary', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Error loading task stats:', error)
    }
  }

  const createTask = async () => {
    try {
      const taskData = {
        title: newTaskForm.title,
        description: newTaskForm.description,
        priority: newTaskForm.priority,
        assigned_agent: newTaskForm.assigned_agent || null,
        due_date: newTaskForm.due_date ? new Date(newTaskForm.due_date).toISOString() : null,
        tags: newTaskForm.tags.split(',').map(tag => tag.trim()).filter(Boolean),
      }

      const response = await fetch('/api/tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify(taskData),
      })

      if (response.ok) {
        const newTask = await response.json()
        setTasks(prev => [newTask, ...prev])
        setShowNewTaskDialog(false)
        setNewTaskForm(INITIAL_FORM)
        loadStats()
      }
    } catch (error) {
      console.error('Error creating task:', error)
    }
  }

  const updateTaskStatus = async (taskId: string, status: Task['status']) => {
    try {
      const response = await fetch(`/api/tasks/${taskId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({ status }),
      })

      if (response.ok) {
        const updatedTask = await response.json()
        setTasks(prev => prev.map(task => 
          task.id === taskId ? updatedTask : task
        ))
        loadStats()
      }
    } catch (error) {
      console.error('Error updating task status:', error)
    }
  }

  const deleteTask = async (taskId: string) => {
    if (!confirm('Are you sure you want to delete this task?')) return

    try {
      const response = await fetch(`/api/tasks/${taskId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        setTasks(prev => prev.filter(task => task.id !== taskId))
        loadStats()
      }
    } catch (error) {
      console.error('Error deleting task:', error)
    }
  }

  const assignTaskToAgent = async (taskId: string, agentId: string) => {
    try {
      const response = await fetch(`/api/tasks/${taskId}/assign/${agentId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const updatedTask = await response.json()
        setTasks(prev => prev.map(task => 
          task.id === taskId ? updatedTask : task
        ))
      }
    } catch (error) {
      console.error('Error assigning task:', error)
    }
  }

  const filteredTasks = tasks
    .filter(task => {
      if (filter === 'all') return true
      if (filter === 'overdue') {
        return task.due_date && new Date(task.due_date) < new Date() && task.status !== 'completed'
      }
      if (filter === 'due_today') {
        const today = new Date().toDateString()
        return task.due_date && new Date(task.due_date).toDateString() === today && task.status !== 'completed'
      }
      return task.status === filter
    })
    .filter(task => 
      searchQuery === '' || 
      task.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.description?.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      // Sort by priority and due date
      const priorityOrder = { high: 3, medium: 2, low: 1 }
      if (a.status !== b.status) {
        const statusOrder = { pending: 3, in_progress: 2, completed: 1 }
        return statusOrder[b.status] - statusOrder[a.status]
      }
      if (a.priority !== b.priority) {
        return priorityOrder[b.priority] - priorityOrder[a.priority]
      }
      if (a.due_date && b.due_date) {
        return new Date(a.due_date).getTime() - new Date(b.due_date).getTime()
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return 'text-red-600 bg-red-100'
      case 'medium': return 'text-yellow-600 bg-yellow-100'
      case 'low': return 'text-green-600 bg-green-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100'
      case 'in_progress': return 'text-blue-600 bg-blue-100'
      case 'pending': return 'text-gray-600 bg-gray-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  const isOverdue = (task: Task) => {
    return task.due_date && new Date(task.due_date) < new Date() && task.status !== 'completed'
  }

  return (
    <div className="bg-white rounded-lg border shadow-sm">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Tasks</h2>
          <Dialog open={showNewTaskDialog} onOpenChange={setShowNewTaskDialog}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="w-4 h-4 mr-2" />
                New Task
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Task</DialogTitle>
              </DialogHeader>
              
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">Title</label>
                  <Input
                    value={newTaskForm.title}
                    onChange={(e) => setNewTaskForm(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="Task title"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">Description</label>
                  <Textarea
                    value={newTaskForm.description}
                    onChange={(e) => setNewTaskForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Task description"
                    rows={3}
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Priority</label>
                    <Select
                      value={newTaskForm.priority}
                      onValueChange={(value: 'low' | 'medium' | 'high') => 
                        setNewTaskForm(prev => ({ ...prev, priority: value }))
                      }
                    >
                      {priorities.map(priority => (
                        <option key={priority} value={priority}>
                          {priority.charAt(0).toUpperCase() + priority.slice(1)}
                        </option>
                      ))}
                    </Select>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-2 block">Assign to Agent</label>
                    <Select
                      value={newTaskForm.assigned_agent}
                      onValueChange={(value) => setNewTaskForm(prev => ({ ...prev, assigned_agent: value }))}
                    >
                      <option value="">Unassigned</option>
                      {agents.slice(1).map(agent => (
                        <option key={agent} value={agent}>
                          {agent.charAt(0).toUpperCase() + agent.slice(1)}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">Due Date</label>
                  <Input
                    type="datetime-local"
                    value={newTaskForm.due_date}
                    onChange={(e) => setNewTaskForm(prev => ({ ...prev, due_date: e.target.value }))}
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">Tags</label>
                  <Input
                    value={newTaskForm.tags}
                    onChange={(e) => setNewTaskForm(prev => ({ ...prev, tags: e.target.value }))}
                    placeholder="Tags separated by commas"
                  />
                </div>
                
                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setShowNewTaskDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={createTask}>
                    Create Task
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 text-sm">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.total_tasks}</div>
              <div className="text-gray-600">Total</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.completion_rate.toFixed(0)}%</div>
              <div className="text-gray-600">Completed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{stats.overdue_tasks}</div>
              <div className="text-gray-600">Overdue</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600">{stats.due_today}</div>
              <div className="text-gray-600">Due Today</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex space-x-2">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <Input
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          
          <Select value={filter} onValueChange={setFilter}>
            <option value="all">All Tasks</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="overdue">Overdue</option>
            <option value="due_today">Due Today</option>
          </Select>
        </div>
      </div>

      {/* Task List */}
      <div className="max-h-96 overflow-auto">
        {isLoading ? (
          <div className="flex justify-center items-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {searchQuery ? 'No tasks match your search' : 'No tasks found'}
          </div>
        ) : (
          <div className="divide-y">
            {filteredTasks.map((task) => (
              <div key={task.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3 flex-1 min-w-0">
                    <button
                      onClick={() => updateTaskStatus(
                        task.id, 
                        task.status === 'completed' ? 'pending' : 'completed'
                      )}
                      className={`mt-1 w-5 h-5 rounded border-2 flex items-center justify-center ${
                        task.status === 'completed'
                          ? 'bg-green-500 border-green-500 text-white'
                          : 'border-gray-300 hover:border-gray-400'
                      }`}
                    >
                      {task.status === 'completed' && <Check className="w-3 h-3" />}
                    </button>
                    
                    <div className="flex-1 min-w-0">
                      <div className={`font-medium ${
                        task.status === 'completed' ? 'line-through text-gray-500' : ''
                      }`}>
                        {task.title}
                        {isOverdue(task) && <AlertCircle className="w-4 h-4 inline ml-2 text-red-500" />}
                      </div>
                      
                      {task.description && (
                        <div className="text-sm text-gray-600 mt-1 line-clamp-2">
                          {task.description}
                        </div>
                      )}
                      
                      <div className="flex items-center space-x-2 mt-2">
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          getPriorityColor(task.priority)
                        }`}>
                          {task.priority}
                        </span>
                        
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          getStatusColor(task.status)
                        }`}>
                          {task.status.replace('_', ' ')}
                        </span>
                        
                        {task.assigned_agent && (
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            <User className="w-3 h-3 mr-1" />
                            {task.assigned_agent}
                          </span>
                        )}
                      </div>
                      
                      <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                        {task.due_date && (
                          <span className={`flex items-center ${isOverdue(task) ? 'text-red-500' : ''}`}>
                            <Calendar className="w-3 h-3 mr-1" />
                            Due {formatDate(task.due_date)}
                          </span>
                        )}
                        
                        <span className="flex items-center">
                          <Clock className="w-3 h-3 mr-1" />
                          {formatTimeAgo(task.created_at)}
                        </span>
                        
                        {task.tags.length > 0 && (
                          <span className="flex items-center">
                            <Tag className="w-3 h-3 mr-1" />
                            {task.tags.slice(0, 2).join(', ')}
                            {task.tags.length > 2 && '...'}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-1 ml-4">
                    {!task.assigned_agent && (
                      <Select
                        value=""
                        onValueChange={(agentId) => assignTaskToAgent(task.id, agentId)}
                      >
                        <option value="">Assign to...</option>
                        {agents.slice(1).map(agent => (
                          <option key={agent} value={agent}>
                            {agent.charAt(0).toUpperCase() + agent.slice(1)}
                          </option>
                        ))}
                      </Select>
                    )}
                    
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteTask(task.id)}
                      className="text-red-500 hover:text-red-700"
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
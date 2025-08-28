"use client"

import React, { useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight, Plus, Calendar, Clock, MapPin, Users, Settings, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { formatDate, formatTime } from '@/lib/utils'

interface CalendarEvent {
  id: string
  title: string
  description?: string
  start_time: string
  end_time: string
  all_day: boolean
  location?: string
  attendees: string[]
  reminder_minutes?: number
  created_by_agent?: string
  metadata?: Record<string, any>
}

interface NewEventForm {
  title: string
  description: string
  start_date: string
  start_time: string
  end_date: string
  end_time: string
  all_day: boolean
  location: string
  attendees: string
  reminder_minutes: number
}

const INITIAL_FORM: NewEventForm = {
  title: '',
  description: '',
  start_date: new Date().toISOString().split('T')[0],
  start_time: '09:00',
  end_date: new Date().toISOString().split('T')[0],
  end_time: '10:00',
  all_day: false,
  location: '',
  attendees: '',
  reminder_minutes: 15,
}

export default function CalendarWidget() {
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [currentDate, setCurrentDate] = useState(new Date())
  const [selectedDate, setSelectedDate] = useState<Date | null>(null)
  const [showNewEventDialog, setShowNewEventDialog] = useState(false)
  const [newEventForm, setNewEventForm] = useState<NewEventForm>(INITIAL_FORM)
  const [isLoading, setIsLoading] = useState(false)
  const [view, setView] = useState<'month' | 'week' | 'day'>('month')

  useEffect(() => {
    loadEvents()
  }, [currentDate, view])

  const loadEvents = async () => {
    setIsLoading(true)
    try {
      const startOfMonth = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1)
      const endOfMonth = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0)

      const params = new URLSearchParams({
        start_date: startOfMonth.toISOString(),
        end_date: endOfMonth.toISOString(),
        limit: '100',
      })

      const response = await fetch(`/api/calendar/events?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setEvents(data)
      }
    } catch (error) {
      console.error('Error loading events:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const createEvent = async () => {
    try {
      const startDateTime = newEventForm.all_day
        ? new Date(newEventForm.start_date)
        : new Date(`${newEventForm.start_date}T${newEventForm.start_time}`)

      const endDateTime = newEventForm.all_day
        ? new Date(newEventForm.end_date)
        : new Date(`${newEventForm.end_date}T${newEventForm.end_time}`)

      const eventData = {
        title: newEventForm.title,
        description: newEventForm.description,
        start_time: startDateTime.toISOString(),
        end_time: endDateTime.toISOString(),
        all_day: newEventForm.all_day,
        location: newEventForm.location,
        attendees: newEventForm.attendees.split(',').map(email => email.trim()).filter(Boolean),
        reminder_minutes: newEventForm.reminder_minutes,
      }

      const response = await fetch('/api/calendar/events', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify(eventData),
      })

      if (response.ok) {
        const newEvent = await response.json()
        setEvents(prev => [...prev, newEvent])
        setShowNewEventDialog(false)
        setNewEventForm(INITIAL_FORM)
      }
    } catch (error) {
      console.error('Error creating event:', error)
    }
  }

  const deleteEvent = async (eventId: string) => {
    if (!confirm('Are you sure you want to delete this event?')) return

    try {
      const response = await fetch(`/api/calendar/events/${eventId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        setEvents(prev => prev.filter(event => event.id !== eventId))
      }
    } catch (error) {
      console.error('Error deleting event:', error)
    }
  }

  const exportCalendar = async () => {
    try {
      const response = await fetch('/api/calendar/export/ical', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'calendar.ics'
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (error) {
      console.error('Error exporting calendar:', error)
    }
  }

  const syncGoogleCalendar = async () => {
    try {
      const response = await fetch('/api/calendar/sync/google', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        await loadEvents()
      }
    } catch (error) {
      console.error('Error syncing with Google Calendar:', error)
    }
  }

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear()
    const month = date.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const daysInMonth = lastDay.getDate()
    const startingDayOfWeek = firstDay.getDay()

    const days = []
    
    // Previous month days
    const prevMonth = new Date(year, month - 1, 0)
    for (let i = startingDayOfWeek - 1; i >= 0; i--) {
      days.push({
        date: new Date(year, month - 1, prevMonth.getDate() - i),
        isCurrentMonth: false,
      })
    }

    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
      days.push({
        date: new Date(year, month, day),
        isCurrentMonth: true,
      })
    }

    // Next month days to fill the grid
    const remainingDays = 42 - days.length
    for (let day = 1; day <= remainingDays; day++) {
      days.push({
        date: new Date(year, month + 1, day),
        isCurrentMonth: false,
      })
    }

    return days
  }

  const getEventsForDate = (date: Date) => {
    return events.filter(event => {
      const eventDate = new Date(event.start_time)
      return eventDate.toDateString() === date.toDateString()
    })
  }

  const navigateMonth = (direction: 'prev' | 'next') => {
    setCurrentDate(prev => {
      const newDate = new Date(prev)
      if (direction === 'prev') {
        newDate.setMonth(newDate.getMonth() - 1)
      } else {
        newDate.setMonth(newDate.getMonth() + 1)
      }
      return newDate
    })
  }

  const today = new Date()
  const days = getDaysInMonth(currentDate)
  const monthYear = currentDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  return (
    <div className="bg-white rounded-lg border shadow-sm">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-semibold">Calendar</h2>
          <div className="flex items-center space-x-2">
            <Select value={view} onValueChange={(value: 'month' | 'week' | 'day') => setView(value)}>
              <option value="month">Month</option>
              <option value="week">Week</option>
              <option value="day">Day</option>
            </Select>
            <Button variant="outline" size="sm" onClick={exportCalendar}>
              <Download className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={syncGoogleCalendar}>
              <Settings className="w-4 h-4" />
            </Button>
            <Dialog open={showNewEventDialog} onOpenChange={setShowNewEventDialog}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="w-4 h-4 mr-2" />
                  New Event
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle>Create New Event</DialogTitle>
                </DialogHeader>
                
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Title</label>
                    <Input
                      value={newEventForm.title}
                      onChange={(e) => setNewEventForm(prev => ({ ...prev, title: e.target.value }))}
                      placeholder="Event title"
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-2 block">Description</label>
                    <Textarea
                      value={newEventForm.description}
                      onChange={(e) => setNewEventForm(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Event description"
                      rows={3}
                    />
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <Switch
                      checked={newEventForm.all_day}
                      onCheckedChange={(checked) => setNewEventForm(prev => ({ ...prev, all_day: checked }))}
                    />
                    <label className="text-sm">All day event</label>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium mb-2 block">Start Date</label>
                      <Input
                        type="date"
                        value={newEventForm.start_date}
                        onChange={(e) => setNewEventForm(prev => ({ ...prev, start_date: e.target.value }))}
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-2 block">End Date</label>
                      <Input
                        type="date"
                        value={newEventForm.end_date}
                        onChange={(e) => setNewEventForm(prev => ({ ...prev, end_date: e.target.value }))}
                      />
                    </div>
                  </div>
                  
                  {!newEventForm.all_day && (
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-sm font-medium mb-2 block">Start Time</label>
                        <Input
                          type="time"
                          value={newEventForm.start_time}
                          onChange={(e) => setNewEventForm(prev => ({ ...prev, start_time: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label className="text-sm font-medium mb-2 block">End Time</label>
                        <Input
                          type="time"
                          value={newEventForm.end_time}
                          onChange={(e) => setNewEventForm(prev => ({ ...prev, end_time: e.target.value }))}
                        />
                      </div>
                    </div>
                  )}
                  
                  <div>
                    <label className="text-sm font-medium mb-2 block">Location</label>
                    <Input
                      value={newEventForm.location}
                      onChange={(e) => setNewEventForm(prev => ({ ...prev, location: e.target.value }))}
                      placeholder="Event location"
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-2 block">Attendees</label>
                    <Input
                      value={newEventForm.attendees}
                      onChange={(e) => setNewEventForm(prev => ({ ...prev, attendees: e.target.value }))}
                      placeholder="Email addresses, separated by commas"
                    />
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-2 block">Reminder (minutes before)</label>
                    <Select
                      value={newEventForm.reminder_minutes.toString()}
                      onValueChange={(value) => setNewEventForm(prev => ({ ...prev, reminder_minutes: parseInt(value) }))}
                    >
                      <option value="0">No reminder</option>
                      <option value="5">5 minutes</option>
                      <option value="15">15 minutes</option>
                      <option value="30">30 minutes</option>
                      <option value="60">1 hour</option>
                      <option value="1440">1 day</option>
                    </Select>
                  </div>
                  
                  <div className="flex justify-end space-x-2">
                    <Button variant="outline" onClick={() => setShowNewEventDialog(false)}>
                      Cancel
                    </Button>
                    <Button onClick={createEvent}>
                      Create Event
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Month Navigation */}
        <div className="flex justify-between items-center mt-4">
          <Button variant="ghost" size="sm" onClick={() => navigateMonth('prev')}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <h3 className="text-lg font-medium">{monthYear}</h3>
          <Button variant="ghost" size="sm" onClick={() => navigateMonth('next')}>
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Calendar Grid */}
      <div className="p-4">
        {view === 'month' && (
          <div>
            {/* Days of week header */}
            <div className="grid grid-cols-7 gap-1 mb-2">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                <div key={day} className="p-2 text-center text-sm font-medium text-gray-500">
                  {day}
                </div>
              ))}
            </div>

            {/* Calendar days */}
            <div className="grid grid-cols-7 gap-1">
              {days.map((day, index) => {
                const dayEvents = getEventsForDate(day.date)
                const isToday = day.date.toDateString() === today.toDateString()
                const isSelected = selectedDate?.toDateString() === day.date.toDateString()

                return (
                  <div
                    key={index}
                    className={`min-h-[80px] p-1 border rounded cursor-pointer transition-colors ${
                      day.isCurrentMonth
                        ? isSelected
                          ? 'bg-blue-100 border-blue-300'
                          : isToday
                          ? 'bg-blue-50 border-blue-200'
                          : 'bg-white hover:bg-gray-50'
                        : 'bg-gray-50 text-gray-400'
                    }`}
                    onClick={() => setSelectedDate(day.date)}
                  >
                    <div className={`text-sm ${isToday ? 'font-bold text-blue-600' : ''}`}>
                      {day.date.getDate()}
                    </div>
                    
                    {/* Events */}
                    <div className="space-y-1 mt-1">
                      {dayEvents.slice(0, 2).map((event) => (
                        <div
                          key={event.id}
                          className="text-xs p-1 bg-blue-100 text-blue-800 rounded truncate"
                          title={event.title}
                        >
                          {event.all_day ? (
                            event.title
                          ) : (
                            `${formatTime(event.start_time)} ${event.title}`
                          )}
                        </div>
                      ))}
                      {dayEvents.length > 2 && (
                        <div className="text-xs text-gray-500">
                          +{dayEvents.length - 2} more
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Event Details for Selected Date */}
        {selectedDate && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium mb-2">
              Events for {formatDate(selectedDate)}
            </h4>
            
            {getEventsForDate(selectedDate).length === 0 ? (
              <p className="text-gray-500 text-sm">No events scheduled</p>
            ) : (
              <div className="space-y-2">
                {getEventsForDate(selectedDate).map((event) => (
                  <div key={event.id} className="flex justify-between items-start p-2 bg-white rounded border">
                    <div className="flex-1">
                      <div className="font-medium">{event.title}</div>
                      {event.description && (
                        <div className="text-sm text-gray-600 mt-1">{event.description}</div>
                      )}
                      <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                        <span className="flex items-center">
                          <Clock className="w-3 h-3 mr-1" />
                          {event.all_day ? 'All day' : `${formatTime(event.start_time)} - ${formatTime(event.end_time)}`}
                        </span>
                        {event.location && (
                          <span className="flex items-center">
                            <MapPin className="w-3 h-3 mr-1" />
                            {event.location}
                          </span>
                        )}
                        {event.attendees.length > 0 && (
                          <span className="flex items-center">
                            <Users className="w-3 h-3 mr-1" />
                            {event.attendees.length} attendees
                          </span>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteEvent(event.id)}
                      className="text-red-500 hover:text-red-700"
                    >
                      Delete
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
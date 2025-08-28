"use client"

import React, { useState, useEffect } from 'react'
import { Save, RefreshCw, User, Settings, Volume2, Mic, Brain } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Slider } from '@/components/ui/slider'
import { useToast } from '@/components/ui/use-toast'

interface Agent {
  name: string
  nickname: string
  description: string
  persona: string
  voice_id: string
  capabilities: Array<{
    name: string
    description: string
    enabled: boolean
  }>
  voice_settings?: {
    stability: number
    similarity_boost: number
    style: number
    use_speaker_boost: boolean
  }
}

interface Voice {
  voice_id: string
  name: string
  category?: string
  description?: string
  gender?: string
  accent?: string
}

const DEFAULT_AGENT_CONFIG: Agent = {
  name: '',
  nickname: '',
  description: '',
  persona: '',
  voice_id: '',
  capabilities: [],
  voice_settings: {
    stability: 0.5,
    similarity_boost: 0.8,
    style: 0.0,
    use_speaker_boost: true
  }
}

export default function AgentConfig() {
  const [agents, setAgents] = useState<Record<string, Agent>>({})
  const [selectedAgent, setSelectedAgent] = useState<string>('carol')
  const [currentConfig, setCurrentConfig] = useState<Agent>(DEFAULT_AGENT_CONFIG)
  const [availableVoices, setAvailableVoices] = useState<Voice[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isTestingVoice, setIsTestingVoice] = useState(false)
  const [agentStats, setAgentStats] = useState<Record<string, any>>({})
  const { toast } = useToast()

  const agentIds = ['carol', 'alex', 'sofia', 'morgan', 'judy']

  useEffect(() => {
    loadAgentConfigs()
    loadAvailableVoices()
    loadAgentStats()
  }, [])

  useEffect(() => {
    if (agents[selectedAgent]) {
      setCurrentConfig(agents[selectedAgent])
    }
  }, [selectedAgent, agents])

  const loadAgentConfigs = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/agents', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setAgents(data.agents || {})
      } else {
        toast({
          title: "Error",
          description: "Failed to load agent configurations",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error('Error loading agent configs:', error)
      toast({
        title: "Error",
        description: "Failed to load agent configurations",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const loadAvailableVoices = async () => {
    try {
      const response = await fetch('/api/voice/voices/available?mode=online', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        setAvailableVoices(data.voices || [])
      }
    } catch (error) {
      console.error('Error loading voices:', error)
    }
  }

  const loadAgentStats = async () => {
    try {
      const response = await fetch('/api/agents', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        const stats: Record<string, any> = {}
        
        Object.entries(data.agents || {}).forEach(([agentId, agent]: [string, any]) => {
          stats[agentId] = agent.status || {}
        })
        
        setAgentStats(stats)
      }
    } catch (error) {
      console.error('Error loading agent stats:', error)
    }
  }

  const saveAgentConfig = async () => {
    setIsSaving(true)
    try {
      const response = await fetch(`/api/agents/${selectedAgent}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify(currentConfig),
      })

      if (response.ok) {
        setAgents(prev => ({
          ...prev,
          [selectedAgent]: currentConfig
        }))
        
        toast({
          title: "Success",
          description: "Agent configuration saved successfully",
        })
      } else {
        toast({
          title: "Error",
          description: "Failed to save agent configuration",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error('Error saving agent config:', error)
      toast({
        title: "Error",
        description: "Failed to save agent configuration",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  const testVoice = async () => {
    if (!currentConfig.voice_id) return

    setIsTestingVoice(true)
    try {
      const response = await fetch('/api/voice/test-voice', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          voice_id: currentConfig.voice_id,
          mode: 'online',
          text: `Hello, I'm ${currentConfig.name}. ${currentConfig.description}`
        }),
      })

      if (response.ok) {
        const audioBlob = await response.blob()
        const audioUrl = URL.createObjectURL(audioBlob)
        const audio = new Audio(audioUrl)
        audio.play()
        
        audio.onended = () => {
          URL.revokeObjectURL(audioUrl)
        }
      } else {
        toast({
          title: "Error",
          description: "Failed to test voice",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error('Error testing voice:', error)
      toast({
        title: "Error",
        description: "Failed to test voice",
        variant: "destructive",
      })
    } finally {
      setIsTestingVoice(false)
    }
  }

  const resetAgentConfig = async () => {
    if (!confirm('Are you sure you want to reset this agent to default configuration?')) {
      return
    }

    try {
      const response = await fetch(`/api/agents/${selectedAgent}/reset`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (response.ok) {
        await loadAgentConfigs()
        toast({
          title: "Success",
          description: "Agent configuration reset successfully",
        })
      } else {
        toast({
          title: "Error",
          description: "Failed to reset agent configuration",
          variant: "destructive",
        })
      }
    } catch (error) {
      console.error('Error resetting agent:', error)
      toast({
        title: "Error",
        description: "Failed to reset agent configuration",
        variant: "destructive",
      })
    }
  }

  const updateCurrentConfig = (field: keyof Agent, value: any) => {
    setCurrentConfig(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const updateVoiceSettings = (field: string, value: any) => {
    setCurrentConfig(prev => ({
      ...prev,
      voice_settings: {
        ...prev.voice_settings,
        [field]: value
      }
    }))
  }

  const updateCapability = (index: number, field: string, value: any) => {
    setCurrentConfig(prev => ({
      ...prev,
      capabilities: prev.capabilities.map((cap, i) => 
        i === index ? { ...cap, [field]: value } : cap
      )
    }))
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Agent Configuration</h1>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            onClick={loadAgentConfigs}
            disabled={isLoading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            onClick={saveAgentConfig}
            disabled={isSaving}
          >
            <Save className="w-4 h-4 mr-2" />
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>

      <div className="flex space-x-6">
        {/* Agent Selection */}
        <div className="w-64">
          <h3 className="text-lg font-semibold mb-4">Select Agent</h3>
          <div className="space-y-2">
            {agentIds.map((agentId) => {
              const agent = agents[agentId]
              const stats = agentStats[agentId]
              
              return (
                <button
                  key={agentId}
                  className={`w-full p-3 text-left border rounded-lg transition-colors ${
                    selectedAgent === agentId
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => setSelectedAgent(agentId)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">
                        {agent?.name || agentId.charAt(0).toUpperCase() + agentId.slice(1)}
                      </div>
                      <div className="text-sm text-gray-500">
                        {agent?.nickname || agentId}
                      </div>
                    </div>
                    <div className={`w-2 h-2 rounded-full ${
                      stats?.is_initialized ? 'bg-green-500' : 'bg-gray-300'
                    }`} />
                  </div>
                  {stats && (
                    <div className="mt-2 text-xs text-gray-500">
                      {stats.message_count || 0} messages • {stats.error_count || 0} errors
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* Configuration Panel */}
        <div className="flex-1">
          {isLoading ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : (
            <Tabs defaultValue="basic" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Basic Info</TabsTrigger>
                <TabsTrigger value="persona">Persona</TabsTrigger>
                <TabsTrigger value="voice">Voice</TabsTrigger>
                <TabsTrigger value="capabilities">Capabilities</TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Agent Name</label>
                    <Input
                      value={currentConfig.name}
                      onChange={(e) => updateCurrentConfig('name', e.target.value)}
                      placeholder="Enter agent name"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">Nickname</label>
                    <Input
                      value={currentConfig.nickname}
                      onChange={(e) => updateCurrentConfig('nickname', e.target.value)}
                      placeholder="Enter nickname"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">Description</label>
                  <Textarea
                    value={currentConfig.description}
                    onChange={(e) => updateCurrentConfig('description', e.target.value)}
                    placeholder="Describe this agent's role and capabilities"
                    rows={3}
                  />
                </div>
              </TabsContent>

              <TabsContent value="persona" className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">Persona</label>
                  <Textarea
                    value={currentConfig.persona}
                    onChange={(e) => updateCurrentConfig('persona', e.target.value)}
                    placeholder="Define the agent's personality, communication style, and behavior"
                    rows={8}
                  />
                  <p className="text-sm text-gray-500 mt-2">
                    This defines how the agent behaves and responds to users. Be specific about personality traits,
                    communication style, expertise areas, and any behavioral guidelines.
                  </p>
                </div>
              </TabsContent>

              <TabsContent value="voice" className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">Voice Selection</label>
                  <div className="flex space-x-2">
                    <Select
                      value={currentConfig.voice_id}
                      onValueChange={(value) => updateCurrentConfig('voice_id', value)}
                      className="flex-1"
                    >
                      <option value="">Select a voice</option>
                      {availableVoices.map((voice) => (
                        <option key={voice.voice_id} value={voice.voice_id}>
                          {voice.name} {voice.gender && `(${voice.gender})`}
                        </option>
                      ))}
                    </Select>
                    <Button
                      variant="outline"
                      onClick={testVoice}
                      disabled={!currentConfig.voice_id || isTestingVoice}
                    >
                      <Volume2 className="w-4 h-4 mr-2" />
                      {isTestingVoice ? 'Testing...' : 'Test'}
                    </Button>
                  </div>
                </div>

                <div className="space-y-4">
                  <h4 className="text-sm font-medium">Voice Settings</h4>
                  
                  <div>
                    <label className="text-sm text-gray-600 mb-2 block">
                      Stability: {currentConfig.voice_settings?.stability.toFixed(2)}
                    </label>
                    <Slider
                      value={[currentConfig.voice_settings?.stability || 0.5]}
                      onValueChange={([value]) => updateVoiceSettings('stability', value)}
                      min={0}
                      max={1}
                      step={0.01}
                      className="w-full"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Lower values make the voice more expressive and variable
                    </p>
                  </div>

                  <div>
                    <label className="text-sm text-gray-600 mb-2 block">
                      Similarity Boost: {currentConfig.voice_settings?.similarity_boost.toFixed(2)}
                    </label>
                    <Slider
                      value={[currentConfig.voice_settings?.similarity_boost || 0.8]}
                      onValueChange={([value]) => updateVoiceSettings('similarity_boost', value)}
                      min={0}
                      max={1}
                      step={0.01}
                      className="w-full"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Higher values make the voice more similar to the original
                    </p>
                  </div>

                  <div>
                    <label className="text-sm text-gray-600 mb-2 block">
                      Style: {currentConfig.voice_settings?.style.toFixed(2)}
                    </label>
                    <Slider
                      value={[currentConfig.voice_settings?.style || 0.0]}
                      onValueChange={([value]) => updateVoiceSettings('style', value)}
                      min={0}
                      max={1}
                      step={0.01}
                      className="w-full"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Higher values add more stylistic variation
                    </p>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Switch
                      checked={currentConfig.voice_settings?.use_speaker_boost}
                      onCheckedChange={(checked) => updateVoiceSettings('use_speaker_boost', checked)}
                    />
                    <label className="text-sm text-gray-600">Use Speaker Boost</label>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="capabilities" className="space-y-4">
                <div>
                  <h4 className="text-sm font-medium mb-4">Agent Capabilities</h4>
                  <div className="space-y-3">
                    {currentConfig.capabilities.map((capability, index) => (
                      <div key={index} className="flex items-start space-x-3 p-3 border rounded-lg">
                        <Switch
                          checked={capability.enabled}
                          onCheckedChange={(checked) => updateCapability(index, 'enabled', checked)}
                        />
                        <div className="flex-1 min-w-0">
                          <Input
                            value={capability.name}
                            onChange={(e) => updateCapability(index, 'name', e.target.value)}
                            placeholder="Capability name"
                            className="mb-2"
                          />
                          <Textarea
                            value={capability.description}
                            onChange={(e) => updateCapability(index, 'description', e.target.value)}
                            placeholder="Describe what this capability does"
                            rows={2}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  <Button
                    variant="outline"
                    onClick={() => {
                      setCurrentConfig(prev => ({
                        ...prev,
                        capabilities: [
                          ...prev.capabilities,
                          { name: '', description: '', enabled: true }
                        ]
                      }))
                    }}
                    className="w-full"
                  >
                    Add Capability
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          )}

          <div className="mt-6 pt-6 border-t">
            <div className="flex justify-between">
              <Button
                variant="destructive"
                onClick={resetAgentConfig}
              >
                Reset to Default
              </Button>
              
              <div className="flex space-x-2">
                <Button variant="outline">
                  Cancel
                </Button>
                <Button
                  onClick={saveAgentConfig}
                  disabled={isSaving}
                >
                  <Save className="w-4 h-4 mr-2" />
                  {isSaving ? 'Saving...' : 'Save Configuration'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
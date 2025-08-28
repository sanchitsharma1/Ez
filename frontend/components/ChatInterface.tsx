"use client"

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Mic, MicOff, Volume2, VolumeX, Settings, User, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useChatStore } from '@/stores/chatStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useVoice } from '@/hooks/useVoice';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  agentId: string;
  timestamp: Date;
  metadata?: Record<string, any>;
}

interface Agent {
  id: string;
  name: string;
  nickname: string;
  description: string;
  avatar: string;
  status: 'active' | 'busy' | 'offline';
}

const agents: Agent[] = [
  {
    id: 'carol',
    name: 'Carol Garcia',
    nickname: 'Carol',
    description: 'Executive Assistant',
    avatar: '/avatars/carol.png',
    status: 'active'
  },
  {
    id: 'alex',
    name: 'Alex',
    nickname: 'Alex',
    description: 'System Monitor',
    avatar: '/avatars/alex.png',
    status: 'active'
  },
  {
    id: 'sofia',
    name: 'Sofia',
    nickname: 'Sofia',
    description: 'Knowledge Specialist',
    avatar: '/avatars/sofia.png',
    status: 'active'
  },
  {
    id: 'morgan',
    name: 'Morgan',
    nickname: 'Morgan',
    description: 'Financial Analyst',
    avatar: '/avatars/morgan.png',
    status: 'active'
  },
  {
    id: 'judy',
    name: 'Judy',
    nickname: 'Judy',
    description: 'Decision Validator',
    avatar: '/avatars/judy.png',
    status: 'active'
  }
];

export default function ChatInterface() {
  const [message, setMessage] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [mode, setMode] = useState<'online' | 'offline'>('online');
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [speakMode, setSpeakMode] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [currentModel, setCurrentModel] = useState('gpt-4-turbo-preview');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const { 
    messages, 
    isTyping, 
    isConnected, 
    sendMessage, 
    clearMessages,
    setMode: setChatMode,
    setVoiceEnabled: setChatVoiceEnabled
  } = useChatStore();
  
  // WebSocket temporarily disabled - using HTTP API only
  // const { 
  //   connect: connectWebSocket,
  //   disconnect: disconnectWebSocket,
  //   sendWebSocketMessage
  // } = useWebSocket();
  
  const {
    isListening: voiceIsListening,
    isSpeaking: voiceIsSpeaking,
    isSupported: voiceIsSupported,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    synthesizeWithAgent
  } = useVoice();

  // Update local state when voice hook state changes
  useEffect(() => {
    setIsListening(voiceIsListening);
  }, [voiceIsListening]);

  useEffect(() => {
    setIsSpeaking(voiceIsSpeaking);
  }, [voiceIsSpeaking]);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Connect WebSocket on mount - temporarily disabled
  // useEffect(() => {
  //   connectWebSocket();
  //   return () => {
  //     disconnectWebSocket();
  //   };
  // }, [connectWebSocket, disconnectWebSocket]);

  // Handle voice mode
  useEffect(() => {
    setChatVoiceEnabled(voiceEnabled);
  }, [voiceEnabled, setChatVoiceEnabled]);

  // Handle mode change
  useEffect(() => {
    setChatMode(mode);
    loadAvailableModels();
  }, [mode, setChatMode]);

  const loadAvailableModels = async () => {
    try {
      const response = await fetch(`/api/models?mode=${mode}`);
      if (response.ok) {
        const models = await response.json();
        setAvailableModels(models);
      }
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!message.trim()) return;

    const messageText = message;
    setMessage('');

    try {
      await sendMessage({
        message: messageText,
        agent_id: selectedAgent || undefined,
        mode,
        voice_enabled: voiceEnabled
      });

      // If speak mode is enabled, synthesize the response
      if (speakMode && voiceIsSupported) {
        // Wait a bit for the response to be processed
        setTimeout(async () => {
          const lastMessage = messages[messages.length - 1];
          if (lastMessage && lastMessage.role === 'assistant') {
            await synthesizeWithAgent(lastMessage.content, lastMessage.agentId);
          }
        }, 1000);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleVoiceToggle = async () => {
    if (!voiceIsSupported) {
      alert('Voice input is not supported in your browser');
      return;
    }

    if (isListening) {
      stopListening();
    } else {
      try {
        await startListening(
          (transcript: string, isFinal: boolean) => {
            if (isFinal) {
              setMessage(transcript);
              // Automatically send if we have a complete transcript
              if (transcript.trim()) {
                setTimeout(() => handleSendMessage(), 500);
              }
            } else {
              // Show interim results
              setMessage(transcript);
            }
          },
          {
            continuous: true,
            interimResults: true,
            lang: 'en-US'
          }
        );
      } catch (error) {
        console.error('Failed to start voice recognition:', error);
        alert('Failed to start voice recognition. Please check your microphone permissions.');
      }
    }
  };

  const handleSpeakToggle = () => {
    if (isSpeaking) {
      stopSpeaking();
    }
    setSpeakMode(!speakMode);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Handle file upload logic here
    console.log('File uploaded:', file.name);
    // You would typically send this to an API endpoint for processing
  };

  const getAgentInfo = (agentId: string) => {
    return agents.find(agent => agent.id === agentId) || agents[0];
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-500';
      case 'busy': return 'bg-yellow-500';
      case 'offline': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const MessageBubble = ({ message }: { message: Message }) => {
    const isUser = message.role === 'user';
    const agent = getAgentInfo(message.agentId);

    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
      >
        <div className={`flex ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start max-w-[80%] gap-2`}>
          {/* Avatar */}
          <Avatar className="w-8 h-8 flex-shrink-0">
            {isUser ? (
              <AvatarFallback className="bg-blue-500 text-white">
                <User size={16} />
              </AvatarFallback>
            ) : (
              <>
                <AvatarImage src={agent.avatar} alt={agent.name} />
                <AvatarFallback className="bg-purple-500 text-white">
                  <Bot size={16} />
                </AvatarFallback>
              </>
            )}
          </Avatar>

          {/* Message Content */}
          <div className={`rounded-lg px-4 py-2 ${
            isUser 
              ? 'bg-blue-500 text-white' 
              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100'
          }`}>
            {!isUser && (
              <div className="text-xs font-medium mb-1 opacity-70">
                {agent.nickname}
              </div>
            )}
            <div className="text-sm whitespace-pre-wrap">
              {message.content}
            </div>
            <div className="text-xs opacity-50 mt-1">
              {message.timestamp.toLocaleTimeString()}
            </div>
          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Multi-Agent Assistant
          </h1>
          <Badge variant={isConnected ? 'default' : 'destructive'}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          {/* Mode Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Online</span>
            <Switch
              checked={mode === 'offline'}
              onCheckedChange={(checked) => setMode(checked ? 'offline' : 'online')}
            />
            <span className="text-sm font-medium">Offline</span>
          </div>

          {/* Settings Button */}
          <Button
            variant="outline"
            size="icon"
            onClick={() => setShowSettings(!showSettings)}
          >
            <Settings size={18} />
          </Button>
        </div>
      </div>

      {/* Settings Panel */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-4"
          >
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Agent Selection */}
              <div>
                <label className="text-sm font-medium mb-2 block">Select Agent</label>
                <Select value={selectedAgent} onValueChange={setSelectedAgent}>
                  <SelectTrigger>
                    <SelectValue placeholder="Auto-route" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Auto-route</SelectItem>
                    {agents.map(agent => (
                      <SelectItem key={agent.id} value={agent.id}>
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${getStatusColor(agent.status)}`} />
                          {agent.nickname} - {agent.description}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Model Selection */}
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Model ({mode === 'online' ? 'Cloud' : 'Local'})
                </label>
                <Select value={currentModel} onValueChange={setCurrentModel}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {availableModels.length > 0 ? (
                      availableModels.map(model => (
                        <SelectItem key={model} value={model}>
                          {model}
                        </SelectItem>
                      ))
                    ) : (
                      <SelectItem value="loading">Loading models...</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              {/* Voice Settings */}
              <div>
                <label className="text-sm font-medium mb-2 block">Voice Settings</label>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={voiceEnabled}
                      onCheckedChange={setVoiceEnabled}
                      disabled={!voiceIsSupported}
                    />
                    <span className="text-sm">Voice Input</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={speakMode}
                      onCheckedChange={setSpeakMode}
                    />
                    <span className="text-sm">Speak Mode</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4">
        <div className="max-w-4xl mx-auto">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <Bot className="w-16 h-16 mx-auto mb-4 text-gray-400" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                Welcome to Multi-Agent Assistant
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Start a conversation with our AI agents. They can help you with various tasks!
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))
          )}

          {/* Typing Indicator */}
          <AnimatePresence>
            {isTyping && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="flex justify-start mb-4"
              >
                <div className="flex items-start gap-2">
                  <Avatar className="w-8 h-8">
                    <AvatarFallback className="bg-purple-500 text-white">
                      <Bot size={16} />
                    </AvatarFallback>
                  </Avatar>
                  <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-4 py-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-end gap-2">
            {/* Voice Button */}
            {voiceIsSupported && (
              <Button
                variant={isListening ? "default" : "outline"}
                size="icon"
                onClick={handleVoiceToggle}
                className={isListening ? "bg-red-500 hover:bg-red-600" : ""}
                disabled={!voiceEnabled}
              >
                {isListening ? <MicOff size={18} /> : <Mic size={18} />}
              </Button>
            )}

            {/* File Upload Button */}
            <Button
              variant="outline"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
            >
              📎
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleFileUpload}
              accept=".pdf,.txt,.docx,.doc,.wav,.mp3,.mp4"
            />

            {/* Message Input */}
            <div className="flex-1 relative">
              <Input
                ref={inputRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={isListening ? "Listening..." : "Type your message..."}
                className="pr-12"
                disabled={isListening}
              />
              
              {/* Speaking Indicator */}
              {isSpeaking && (
                <div className="absolute right-12 top-1/2 transform -translate-y-1/2">
                  <Volume2 className="w-4 h-4 text-blue-500 animate-pulse" />
                </div>
              )}
            </div>

            {/* Speak Toggle */}
            <Button
              variant={speakMode ? "default" : "outline"}
              size="icon"
              onClick={handleSpeakToggle}
              className={isSpeaking ? "bg-blue-500" : ""}
            >
              {isSpeaking ? <VolumeX size={18} /> : <Volume2 size={18} />}
            </Button>

            {/* Send Button */}
            <Button
              onClick={handleSendMessage}
              disabled={!message.trim() || isTyping}
              size="icon"
            >
              <Send size={18} />
            </Button>
          </div>

          {/* Voice Status */}
          {voiceEnabled && (
            <div className="mt-2 text-xs text-gray-500 text-center">
              {isListening ? "🎤 Listening... (speak now)" : 
               isSpeaking ? "🔊 Speaking..." :
               voiceIsSupported ? "Voice ready" : "Voice not supported"}
            </div>
          )}

          {/* Quick Actions */}
          <div className="flex flex-wrap gap-2 mt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMessage("What's my schedule today?")}
            >
              Check Schedule
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMessage("System status report")}
            >
              System Status
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMessage("Summarize recent documents")}
            >
              Document Summary
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMessage("Show stock market overview")}
            >
              Market Update
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={clearMessages}
            >
              Clear Chat
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
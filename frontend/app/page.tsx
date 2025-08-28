import ChatInterface from '@/components/ChatInterface'
import AgentConfig from '@/components/AgentConfig'
import MemoryManager from '@/components/MemoryManager'
import CalendarWidget from '@/components/CalendarWidget'
import TodoWidget from '@/components/TodoWidget'

export default function Home() {
  return (
    <main className="flex min-h-screen">
      <div className="flex-1 flex flex-col">
        <header className="bg-white shadow-sm border-b px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">SupremeAI</h1>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-500">Multi-Agent Assistant</span>
            </div>
          </div>
        </header>
        
        <div className="flex-1 flex">
          <div className="flex-1">
            <ChatInterface />
          </div>
          
          <div className="w-80 border-l bg-gray-50 p-4 space-y-4">
            <CalendarWidget />
            <TodoWidget />
          </div>
        </div>
      </div>
      
      <div className="w-96 border-l bg-white">
        <div className="p-4">
          <AgentConfig />
          <div className="mt-6">
            <MemoryManager />
          </div>
        </div>
      </div>
    </main>
  )
}
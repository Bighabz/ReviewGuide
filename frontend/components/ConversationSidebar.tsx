'use client'

import { useState, useEffect } from 'react'
import {
  MessageSquare,
  Plus,
  Trash2,
  X,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

interface Conversation {
  session_id: string
  preview: string
  created_at: string
  message_count: number
}

interface ConversationSidebarProps {
  isOpen: boolean
  onClose: () => void
  currentSessionId: string
  onSelectConversation: (sessionId: string) => void
  onNewConversation: () => void
}

export default function ConversationSidebar({
  isOpen,
  onClose,
  currentSessionId,
  onSelectConversation,
  onNewConversation,
}: ConversationSidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) fetchConversations()
  }, [isOpen])

  const fetchConversations = async () => {
    setIsLoading(true)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const allSessionsJson = localStorage.getItem('chat_all_session_ids')
      let allSessions: string[] = allSessionsJson ? JSON.parse(allSessionsJson) : []

      if (currentSessionId && !allSessions.includes(currentSessionId)) {
        allSessions.push(currentSessionId)
        localStorage.setItem('chat_all_session_ids', JSON.stringify(allSessions))
      }

      const url = allSessions.length > 0
        ? `${apiUrl}/v1/chat/conversations?session_ids=${encodeURIComponent(allSessions.join(','))}`
        : `${apiUrl}/v1/chat/conversations`
      const response = await fetch(url)
      if (!response.ok) throw new Error(`Failed to fetch conversations: ${response.status}`)
      const data = await response.json()

      if (data.success && data.conversations) {
        setConversations(data.conversations)
      }
    } catch (error) {
      console.error('Failed to fetch conversations:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    if (deletingId) return

    setDeletingId(sessionId)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/v1/chat/conversations/${sessionId}`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error(`Failed to delete conversation: ${response.status}`)
      const data = await response.json()

      if (data.success) {
        setConversations(prev => prev.filter(c => c.session_id !== sessionId))
        if (sessionId === currentSessionId) {
          onNewConversation()
        }
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    } finally {
      setDeletingId(null)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))

    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    if (days < 7) return `${days}d ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-[60] lg:hidden"
            onClick={onClose}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <div
        className={`
          fixed lg:static inset-y-0 right-0 z-[70]
          w-72 lg:w-64 flex flex-col h-screen
          transform transition-transform duration-300 ease-out
          lg:transform-none shadow-xl lg:shadow-none
          border-l border-[var(--border)]
          ${isOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0 lg:hidden'}
        `}
        style={{ background: 'var(--surface)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
            <MessageSquare size={15} strokeWidth={1.5} className="text-[var(--primary)]" />
            History
          </h2>
          <button
            onClick={onClose}
            aria-label="Close history"
            className="lg:hidden min-w-[40px] min-h-[40px] flex items-center justify-center rounded-lg hover:bg-[var(--surface-hover)] text-[var(--text-muted)]"
          >
            <X size={16} strokeWidth={1.5} />
          </button>
        </div>

        {/* New Chat */}
        <div className="p-3">
          <button
            onClick={() => {
              onNewConversation()
              onClose()
            }}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--primary)] text-white text-sm font-medium hover:bg-[var(--primary-hover)] transition-all active:scale-[0.97]"
          >
            <Plus size={16} strokeWidth={2} />
            New Chat
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto px-2 pb-3">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-10 gap-2">
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-[var(--primary)] border-t-transparent" />
              <span className="text-xs text-[var(--text-muted)]">Loading...</span>
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-12 px-4">
              <div className="w-10 h-10 rounded-full bg-[var(--surface-hover)] flex items-center justify-center mx-auto mb-3">
                <MessageSquare size={18} strokeWidth={1.5} className="text-[var(--text-muted)]" />
              </div>
              <p className="text-sm font-medium text-[var(--text)]">No conversations</p>
              <p className="text-xs mt-1 text-[var(--text-muted)]">
                Your chat history will appear here.
              </p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {conversations.map((conv) => {
                const isActive = conv.session_id === currentSessionId
                return (
                  <motion.div
                    key={conv.session_id}
                    layoutId={`conv-${conv.session_id}`}
                    onClick={() => {
                      onSelectConversation(conv.session_id)
                      onClose()
                    }}
                    className={`
                      group relative flex items-start gap-2 px-3 py-2.5 rounded-lg cursor-pointer
                      transition-all
                      ${isActive
                        ? 'bg-[var(--surface-hover)] border border-[var(--border)]'
                        : 'border border-transparent hover:bg-[var(--surface-hover)]'
                      }
                    `}
                  >
                    {/* Active indicator */}
                    {isActive && (
                      <motion.div
                        layoutId="active-indicator"
                        className="absolute left-0 top-2.5 bottom-2.5 w-0.5 rounded-r-full bg-[var(--primary)]"
                      />
                    )}

                    <div className="flex-1 min-w-0 pl-1">
                      <p
                        className={`text-sm truncate leading-snug ${isActive
                          ? 'text-[var(--text)] font-semibold'
                          : 'text-[var(--text-secondary)]'
                          }`}
                      >
                        {conv.preview || 'New Conversation'}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="text-[10px] text-[var(--text-muted)]">
                          {formatDate(conv.created_at)}
                        </span>
                        {conv.message_count > 0 && (
                          <>
                            <span className="text-[8px] text-[var(--border-strong)]">&middot;</span>
                            <span className="text-[10px] text-[var(--text-muted)]">
                              {conv.message_count} msg
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Delete */}
                    <button
                      onClick={(e) => handleDelete(e, conv.session_id)}
                      className="p-1 rounded-md opacity-0 group-hover:opacity-100 transition-all text-[var(--text-muted)] hover:text-[var(--error)] hover:bg-[var(--error)]/5"
                    >
                      {deletingId === conv.session_id ? (
                        <div className="animate-spin rounded-full h-3.5 w-3.5 border border-current border-t-transparent" />
                      ) : (
                        <Trash2 size={13} strokeWidth={1.5} />
                      )}
                    </button>
                  </motion.div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[var(--border)]">
          <p className="text-[10px] text-center text-[var(--text-muted)]">
            {conversations.length} conversation{conversations.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>
    </>
  )
}

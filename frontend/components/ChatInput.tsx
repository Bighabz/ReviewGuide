'use client'

import { ArrowUp } from 'lucide-react'
import { useRef, useEffect, useState } from 'react'
import { motion } from 'framer-motion'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled?: boolean
  placeholder?: string
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  disabled = false,
  placeholder = 'Ask about products, travel, or deals...',
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [isFocused, setIsFocused] = useState(false)

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  const adjustHeight = () => {
    const textarea = textareaRef.current
    if (textarea) {
      const maxHeight = 240
      textarea.style.height = '52px'
      textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px'
    }
  }

  useEffect(() => {
    adjustHeight()
  }, [value])

  const hasValue = value.trim().length > 0

  return (
    <div className="w-full relative">
      <div
        className={`relative rounded-[28px] border transition-all duration-200 shadow-rg-card ${isFocused
          ? 'border-[var(--terra)]/40'
          : 'border-[var(--line-2)]'
          }`}
        style={{ background: 'var(--paper-hi)' }}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
            adjustHeight()
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="w-full resize-none rounded-[28px] pl-5 pr-14 py-4 bg-transparent focus:outline-none disabled:cursor-not-allowed text-[15px] leading-[22px] text-[var(--ink)] placeholder:text-[var(--ink-3)]"
          style={{
            minHeight: '52px',
            maxHeight: '240px',
            overflowY: 'auto',
            lineHeight: '1.5',
          }}
        />

        {/* Send Button — 36px ink circle, paper arrow */}
        <motion.button
          onClick={() => onSend()}
          disabled={disabled || !hasValue}
          className="absolute right-2.5 bottom-2.5 rounded-full w-9 h-9 flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed"
          style={{
            // Always a visible dark-ish circle; full ink once there's text to send
            background: hasValue && !disabled ? 'var(--ink)' : 'var(--line-2)',
            color: 'var(--paper)',
          }}
          whileHover={hasValue && !disabled ? { scale: 1.05 } : {}}
          whileTap={hasValue && !disabled ? { scale: 0.92 } : {}}
        >
          <ArrowUp size={18} strokeWidth={2.5} />
        </motion.button>
      </div>

      {/* Footer hint */}
      <div className="hidden sm:flex items-center justify-center gap-1.5 mt-2.5 text-[11px] text-[var(--text-muted)]">
        <span>ReviewGuide AI can make mistakes. Verify important information.</span>
      </div>
    </div>
  )
}

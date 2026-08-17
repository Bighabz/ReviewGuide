'use client'

interface ErrorBannerProps {
  message: string
  onRetry: () => void
  disabled?: boolean
}

export default function ErrorBanner({ message, onRetry, disabled }: ErrorBannerProps) {
  return (
    <div
      className="flex flex-col items-center justify-center py-3 px-4 mx-auto my-3 rounded-lg"
      style={{
        background: 'rgba(217, 45, 32, 0.1)',
        border: '1px solid rgba(217, 45, 32, 0.3)',
        maxWidth: '600px',
      }}
    >
      <div className="flex items-start gap-3 w-full">
        <div
          className="flex-shrink-0 mt-0.5"
          style={{ color: '#d92d20' }}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="10" cy="10" r="8" />
            <line x1="10" y1="6" x2="10" y2="10" />
            <circle cx="10" cy="14" r="0.5" fill="currentColor" />
          </svg>
        </div>

        <div className="flex-1">
          <p
            className="text-sm leading-relaxed whitespace-pre-line"
            style={{ color: '#d92d20' }}
          >
            {message}
          </p>
        </div>
      </div>

      <button
        onClick={onRetry}
        disabled={disabled}
        title={disabled ? 'Still finishing the last request…' : undefined}
        className="mt-3 px-4 py-2 rounded-md text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          background: 'transparent',
          border: '1px solid rgba(217, 45, 32, 0.5)',
          color: '#d92d20',
          cursor: disabled ? 'not-allowed' : 'pointer',
        }}
        onMouseEnter={(e) => {
          if (!disabled) e.currentTarget.style.background = 'rgba(217, 45, 32, 0.1)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent'
        }}
      >
        Regenerate
      </button>
    </div>
  )
}

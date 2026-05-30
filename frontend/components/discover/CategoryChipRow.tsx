'use client'

import { useRouter } from 'next/navigation'

interface ChipConfig {
  label: string
  query?: string // if absent, navigates to /chat?new=1
}

const CHIPS: ChipConfig[] = [
  { label: 'Popular', query: 'Best products of 2026' },
  { label: 'Tech', query: 'Best laptops for productivity' },
  { label: 'Travel', query: 'Top all-inclusive resorts in the Caribbean' },
  { label: 'Kitchen', query: 'Best kitchen appliances 2026' },
  { label: 'Fitness', query: 'Best running shoes 2026' },
  { label: 'Home', query: 'Best Alexa-compatible smart home gadgets' },
  { label: 'Fashion', query: 'Best white sneakers for everyday wear' },
  { label: 'Outdoor', query: 'Best camping gear for beginners' },
]

const FOR_YOU_CHIP: ChipConfig = { label: 'For You' }

interface Props {
  hasHistory: boolean
}

export default function CategoryChipRow({ hasHistory }: Props) {
  const router = useRouter()

  const chips = hasHistory ? [FOR_YOU_CHIP, ...CHIPS] : CHIPS

  function handleChipClick(chip: ChipConfig) {
    if (chip.query) {
      router.push(`/chat?q=${encodeURIComponent(chip.query)}&new=1`)
    } else {
      router.push('/chat?new=1')
    }
  }

  return (
    <div>
      <div className="rg-eyebrow mb-3">Trending right now</div>
      <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
        {chips.map((chip) => {
          const isForYou = chip.label === 'For You'
          return (
            <button
              key={chip.label}
              onClick={() => handleChipClick(chip)}
              className="flex-shrink-0 transition-colors"
              style={{
                height: '34px',
                padding: '0 14px',
                borderRadius: '12px',
                background: isForYou ? 'var(--terra-soft)' : 'var(--paper-hi)',
                border: `1px solid ${isForYou ? 'var(--terra)' : 'var(--line-2)'}`,
                color: isForYou ? 'var(--terra-ink)' : 'var(--ink)',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {chip.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

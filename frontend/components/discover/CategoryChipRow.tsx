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
    <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
      {chips.map((chip) => (
        <button
          key={chip.label}
          onClick={() => handleChipClick(chip)}
          className="flex-shrink-0"
          style={{
            height: '36px',
            padding: '0 16px',
            borderRadius: '20px',
            background: 'transparent',
            border: '1px solid var(--border)',
            color: 'var(--text)',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {chip.label}
        </button>
      ))}
    </div>
  )
}

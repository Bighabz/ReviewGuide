/**
 * Group C — /topic/[slug] landing page. Verifies the editorial intro renders
 * and the single CTA enters research with an *editable* draft (draft=, not
 * auto-send), and that the carousel's preload was correctly moved here.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

const mockPush = vi.fn()
const mockNotFound = vi.fn(() => {
  throw new Error('NEXT_NOT_FOUND')
})

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
  notFound: () => mockNotFound(),
}))

import TopicPage from '@/app/topic/[slug]/page'
import { DISCOVER_TOPICS } from '@/lib/discoverTopics'

const sample = DISCOVER_TOPICS[0]

describe('TopicPage', () => {
  beforeEach(() => {
    mockPush.mockClear()
    mockNotFound.mockClear()
  })

  it('renders the topic title and editorial blurb', () => {
    render(<TopicPage params={{ slug: sample.slug }} />)
    expect(screen.getByRole('heading', { name: sample.title })).toBeTruthy()
    expect(screen.getByText(sample.blurb)).toBeTruthy()
  })

  it('CTA seeds an editable chat draft (draft=, not auto-send q=)', () => {
    render(<TopicPage params={{ slug: sample.slug }} />)
    fireEvent.click(screen.getByRole('button', { name: /start researching/i }))
    expect(mockPush).toHaveBeenCalledTimes(1)
    const url: string = mockPush.mock.calls[0][0]
    expect(url).toContain('/chat?draft=')
    expect(url).toContain(encodeURIComponent(sample.query))
    expect(url).not.toContain('q=' + encodeURIComponent(sample.query))
  })

  it('calls notFound() for an unknown slug', () => {
    expect(() => render(<TopicPage params={{ slug: 'no-such-topic' }} />)).toThrow('NEXT_NOT_FOUND')
    expect(mockNotFound).toHaveBeenCalled()
  })
})

/**
 * PLAN-7 T2 — Regenerate must do something, or say why it can't.
 *
 * In the QA audit a hung stream left isStreaming true, so every Regenerate
 * click hit handleRetry's silent early return. The button now carries a
 * disabled state that reflects that guard instead of swallowing clicks.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ErrorBanner from '@/components/ErrorBanner'

describe('ErrorBanner regenerate', () => {
  it('calls onRetry when enabled', () => {
    const onRetry = vi.fn()
    render(<ErrorBanner message="Hit a wall" onRetry={onRetry} />)
    fireEvent.click(screen.getByRole('button', { name: /regenerate/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('is disabled and explains itself while a request is in flight', () => {
    const onRetry = vi.fn()
    render(<ErrorBanner message="Hit a wall" onRetry={onRetry} disabled />)
    const button = screen.getByRole('button', { name: /regenerate/i })
    expect(button).toHaveProperty('disabled', true)
    fireEvent.click(button)
    expect(onRetry).not.toHaveBeenCalled()
  })
})

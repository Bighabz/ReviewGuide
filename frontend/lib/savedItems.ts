'use client'

// Saved-items + compare-selection store — localStorage backed, with a change event
// so any mounted component (Saved grid, tab-bar badge, save toggles) stays in sync.
// This is the data model the blueprint's Saved (§5.8) and Compare (§5.9) screens read.

import { useEffect, useState } from 'react'

export interface SavedItem {
  id: string
  name: string
  price?: number
  imageUrl?: string
  url?: string
  role?: string
  savedAt: number
}

const ITEMS_KEY = 'saved_items'
const COMPARE_KEY = 'compare_selection'
const CHANGE_EVENT = 'saveditems:changed'

export function slugifyProduct(name: string): string {
  return name.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'item'
}

function emitChange() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT))
  }
}

// ── Saved items ──────────────────────────────────────────────
function readItems(): SavedItem[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(ITEMS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeItems(items: SavedItem[]) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(ITEMS_KEY, JSON.stringify(items))
    emitChange()
  } catch {
    /* quota / serialization — non-fatal */
  }
}

export function getSavedItems(): SavedItem[] {
  return readItems().sort((a, b) => b.savedAt - a.savedAt)
}

export function isSaved(id: string): boolean {
  return readItems().some((i) => i.id === id)
}

/** Toggle save state for an item. Returns the new saved state (true = now saved). */
export function toggleSaved(item: Omit<SavedItem, 'savedAt'>): boolean {
  const items = readItems()
  const idx = items.findIndex((i) => i.id === item.id)
  if (idx >= 0) {
    items.splice(idx, 1)
    writeItems(items)
    // dropping a saved item also drops it from any compare selection
    setCompareSelection(getCompareSelection().filter((cid) => cid !== item.id))
    return false
  }
  items.push({ ...item, savedAt: Date.now() })
  writeItems(items)
  return true
}

export function removeSaved(id: string) {
  writeItems(readItems().filter((i) => i.id !== id))
  setCompareSelection(getCompareSelection().filter((cid) => cid !== id))
}

// ── Compare selection (ids of saved items chosen to compare) ──
function readCompare(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(COMPARE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function setCompareSelection(ids: string[]) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(COMPARE_KEY, JSON.stringify(ids))
    emitChange()
  } catch {
    /* non-fatal */
  }
}

export function getCompareSelection(): string[] {
  return readCompare()
}

/** Toggle an id in the compare selection (cap of 2 — blueprint compares two). Returns new selection. */
export function toggleCompare(id: string): string[] {
  const sel = readCompare()
  let next: string[]
  if (sel.includes(id)) {
    next = sel.filter((c) => c !== id)
  } else {
    next = [...sel, id].slice(-2) // keep the two most-recent
  }
  setCompareSelection(next)
  return next
}

// ── React hook — live view of the store ──────────────────────
export function useSavedItems() {
  const [items, setItems] = useState<SavedItem[]>([])
  const [compare, setCompare] = useState<string[]>([])

  useEffect(() => {
    const sync = () => {
      setItems(getSavedItems())
      setCompare(getCompareSelection())
    }
    sync()
    window.addEventListener(CHANGE_EVENT, sync)
    window.addEventListener('storage', sync) // cross-tab
    return () => {
      window.removeEventListener(CHANGE_EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  return { items, compare }
}

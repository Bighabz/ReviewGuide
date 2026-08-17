// Words a sentence cannot legitimately end on. A completed answer ending in
// "if you have" is a truncation, not a style choice.
const DANGLING = new Set([
  'and', 'or', 'but', 'if', 'the', 'a', 'an', 'to', 'for', 'with', 'have', 'has',
  'is', 'are', 'was', 'were', 'of', 'in', 'on', 'at', 'that', 'than', 'from',
])

/** Heuristic: does this assistant prose look cut off mid-sentence? */
export function isLikelyTruncated(text: string): boolean {
  const trimmed = (text ?? '').trim()
  if (!trimmed) return false

  const lastLine = trimmed.split('\n').filter(Boolean).pop() ?? ''
  // Structured trailing content (list item, table row) is a legitimate ending.
  if (/^\s*(?:[-*•]|\||\d+[.)])/.test(lastLine)) return false
  // Terminal punctuation, including closing quotes/brackets after it.
  if (/[.!?:;][)"'\]]*$/.test(trimmed)) return false

  const lastWord = (trimmed.match(/[A-Za-z']+$/)?.[0] ?? '').toLowerCase()
  return lastWord.length > 0 && (DANGLING.has(lastWord) || !/[.!?]/.test(trimmed.slice(-80)))
}

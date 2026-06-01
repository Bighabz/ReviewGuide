'use client'

import { motion } from 'framer-motion'
import { usePathname } from 'next/navigation'

export default function Template({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  // /chat needs a definite height (h-full) so its inner h-full/overflow-hidden
  // chain keeps the input pinned and the message list scrolling internally.
  // Every other route uses min-h-full: fills the viewport on short pages, but
  // grows on long ones so the footer (last child of <main>) sits at the true
  // bottom of the content instead of being overlapped by it.
  const isChat = !!pathname?.startsWith('/chat')
  return (
    <motion.div
      className={isChat ? 'h-full' : 'min-h-full'}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  )
}

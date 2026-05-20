import { redirect } from 'next/navigation'

// The homepage IS the Discover page (app/page.tsx exports DiscoverPage), and the
// nav links to "/". This redirect only exists so users who type /discover directly
// don't hit a 404. Mirrors the existing /browse -> / redirect.
export default function DiscoverRedirect() {
  redirect('/')
}

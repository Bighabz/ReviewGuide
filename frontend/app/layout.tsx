import NavLayout from '@/components/NavLayout'
import type { Metadata, Viewport } from 'next'
import { DM_Sans, Instrument_Serif, Newsreader } from 'next/font/google'
import './globals.css'

const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-dm-sans', weight: ['400', '500', '600', '700'] })
const instrumentSerif = Instrument_Serif({ subsets: ['latin'], variable: '--font-instrument', weight: '400', style: ['normal', 'italic'] })
// Newsreader — blueprint editorial body face (blog prose, spec rows, product names)
const newsreader = Newsreader({ subsets: ['latin'], variable: '--font-newsreader', weight: ['400', '500', '600'], style: ['normal', 'italic'] })

const SITE_URL = 'https://www.reviewguide.ai'
const TAGLINE =
  'Ask before you buy — AI-powered product research, real review consensus, and price comparison in one chat.'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'ReviewGuide.ai — Ask Before You Buy',
    template: '%s · ReviewGuide.ai',
  },
  description: TAGLINE,
  applicationName: 'ReviewGuide.ai',
  // app/opengraph-image.png and app/twitter-image.png supply the 1200×630 share
  // cards automatically (Next emits og:image / twitter:image with dimensions).
  openGraph: {
    type: 'website',
    url: SITE_URL,
    siteName: 'ReviewGuide.ai',
    title: 'ReviewGuide.ai — Ask Before You Buy',
    description: TAGLINE,
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ReviewGuide.ai — Ask Before You Buy',
    description: TAGLINE,
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  viewportFit: 'cover',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0a0e1a' }
  ],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const theme = localStorage.getItem('theme') || 'light';
                document.documentElement.setAttribute('data-theme', theme);
              } catch (e) {}
            `,
          }}
        />
      </head>
      <body className={`${dmSans.variable} ${instrumentSerif.variable} ${newsreader.variable} font-sans`} suppressHydrationWarning>
        <NavLayout>{children}</NavLayout>
      </body>
    </html>
  )
}

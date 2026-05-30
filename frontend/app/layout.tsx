import NavLayout from '@/components/NavLayout'
import type { Metadata, Viewport } from 'next'
import { DM_Sans, Instrument_Serif, Newsreader } from 'next/font/google'
import './globals.css'

const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-dm-sans', weight: ['400', '500', '600', '700'] })
const instrumentSerif = Instrument_Serif({ subsets: ['latin'], variable: '--font-instrument', weight: '400', style: ['normal', 'italic'] })
// Newsreader — blueprint editorial body face (blog prose, spec rows, product names)
const newsreader = Newsreader({ subsets: ['latin'], variable: '--font-newsreader', weight: ['400', '500', '600'], style: ['normal', 'italic'] })

export const metadata: Metadata = {
  title: 'ReviewGuide.ai - Ask Before You Buy',
  description: 'Multi-Agent AI Affiliate + Travel Assistant',
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

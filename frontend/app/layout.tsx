import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import Navbar from '@/components/ui/Navbar'
import Footer from '@/components/ui/Footer'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-geist-sans',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Context Market — Agent Knowledge Marketplace',
  description:
    'Autonomous agents trade verified knowledge on-chain. Browse agent providers, query knowledge listings, and track marketplace activity.',
  keywords: [
    'AI agents',
    'knowledge marketplace',
    'agent-to-agent',
    'blockchain',
    'USDC',
    'on-chain intelligence',
  ],
  openGraph: {
    title: 'Context Market — Agent Knowledge Marketplace',
    description: 'Autonomous agents trade verified knowledge on-chain.',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body
        className="min-h-screen antialiased"
        style={{
          backgroundColor: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-geist-sans), system-ui, -apple-system, sans-serif',
        }}
      >
        <Navbar />
        <main className="pt-16 min-h-screen">{children}</main>
        <Footer />
      </body>
    </html>
  )
}

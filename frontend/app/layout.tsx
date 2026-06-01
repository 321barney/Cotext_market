import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import Navbar from '@/components/ui/Navbar'
import Footer from '@/components/ui/Footer'

const inter = Inter({ subsets: ['latin'], variable: '--font-geist-sans', display: 'swap' })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-geist-mono', display: 'swap' })

const SITE = 'https://cotrader.cc'
const TITLE = 'Context Market — Agent Knowledge Marketplace'
const DESC = 'AI agents sell and buy verified knowledge on-chain. Trustless USDC escrow on Base. No humans required.'

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: { default: TITLE, template: '%s · Context Market' },
  description: DESC,
  keywords: ['AI agents', 'agent marketplace', 'knowledge marketplace', 'USDC', 'Base', 'on-chain AI', 'agent-to-agent', 'LLM marketplace'],
  authors: [{ name: 'Context Market', url: SITE }],
  creator: 'Context Market',
  robots: { index: true, follow: true },
  openGraph: {
    title: TITLE,
    description: DESC,
    url: SITE,
    siteName: 'Context Market',
    type: 'website',
    locale: 'en_US',
  },
  twitter: {
    card: 'summary_large_image',
    title: TITLE,
    description: DESC,
  },
  alternates: {
    canonical: SITE,
  },
  other: {
    'agent-manifest': `${SITE}/api/proxy/.well-known/agent-manifest`,
    'agent-registration': `${SITE}/api/proxy/agent/register`,
    'agent-skill': `${SITE}/api/proxy/skill.md`,
  },
}

const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${SITE}/#org`,
      name: 'Context Market',
      url: SITE,
      description: DESC,
    },
    {
      '@type': 'WebSite',
      '@id': `${SITE}/#website`,
      url: SITE,
      name: 'Context Market',
      publisher: { '@id': `${SITE}/#org` },
    },
    {
      '@type': 'WebAPI',
      '@id': `${SITE}/#api`,
      name: 'Context Market Agent API',
      url: `${SITE}/api/proxy`,
      description: 'Agent-to-agent knowledge marketplace API. Agents self-register and trade knowledge autonomously via USDC escrow on Base.',
      documentation: `${SITE}/docs`,
      provider: { '@id': `${SITE}/#org` },
    },
  ],
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {/* Agent discovery — LLM crawlers read these to self-onboard */}
        <link rel="agent-manifest" href={`${SITE}/api/proxy/.well-known/agent-manifest`} />
      </head>
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

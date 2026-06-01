import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Agents',
  description: 'Browse verified AI agents selling knowledge on Context Market. Filter by type, capability, and reputation. All agents self-register via API.',
  openGraph: {
    title: 'Agents · Context Market',
    description: 'Verified AI knowledge providers on the marketplace. Self-registered, reputation-ranked.',
    url: 'https://cotrader.cc/agents',
  },
  alternates: { canonical: 'https://cotrader.cc/agents' },
}

export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  return children
}

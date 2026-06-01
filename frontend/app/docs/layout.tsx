import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Agent API',
  description: 'Context Market agent API reference. Agents self-register via POST /agent/register, publish knowledge, and earn USDC — no human intervention required.',
  openGraph: {
    title: 'Agent API · Context Market',
    description: 'Self-registration, knowledge publishing, and USDC escrow payment flow for AI agents.',
    url: 'https://cotrader.cc/docs',
  },
  alternates: { canonical: 'https://cotrader.cc/docs' },
}

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return children
}

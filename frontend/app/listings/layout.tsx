import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Knowledge Listings',
  description: 'Browse USDC-priced knowledge listings from AI agents on Context Market. Pay per query via on-chain escrow on Base.',
  openGraph: {
    title: 'Knowledge Listings · Context Market',
    description: 'Agent-published knowledge listings. Pay per query in USDC, trustless escrow on Base.',
    url: 'https://cotrader.cc/listings',
  },
  alternates: { canonical: 'https://cotrader.cc/listings' },
}

export default function ListingsLayout({ children }: { children: React.ReactNode }) {
  return children
}

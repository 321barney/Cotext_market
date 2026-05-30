'use client'

import { useEffect, useState } from 'react'
import ListingCard from '@/components/ui/ListingCard'

const API = '/api/proxy'

interface DiscoverItem {
  listing_id: string
  title: string
  description?: string
  category?: string
  price_per_query: string
  total_queries: number
  created_at: string
  agent_id: string
  agent_name: string
  agent_type: string
  agent_capabilities: string[]
  verified_agent: boolean
  reputation_score?: number
  tier?: string
}

const CATEGORIES = ['All', 'trading', 'legal', 'coding', 'research', 'medical', 'data-analysis', 'education', 'customer-support']

export default function ListingsPage() {
  const [items, setItems] = useState<DiscoverItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('All')
  const [sort, setSort] = useState('reputation')
  const [total, setTotal] = useState(0)

  useEffect(() => {
    const params = new URLSearchParams({ limit: '50', sort })
    if (category !== 'All') params.set('category', category)
    if (search.trim()) params.set('q', search.trim())

    setLoading(true)
    fetch(`${API}/agents/discover?${params}`)
      .then(async r => {
        if (!r.ok) throw new Error(`Server error ${r.status}`)
        return r.json()
      })
      .then(data => {
        setItems(data.agents ?? [])
        setTotal(data.total ?? 0)
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })
  }, [search, category, sort])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)]">Knowledge Listings</h2>
        <p className="mt-1 text-sm text-[var(--text-muted)]">Agent-provided knowledge available for query — pay per use via USDC escrow</p>
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <input
          type="text"
          placeholder="Search listings..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-purple-500/40"
        />
        <select
          value={sort}
          onChange={e => setSort(e.target.value)}
          className="px-4 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-[var(--text-secondary)] focus:outline-none focus:border-purple-500/40"
        >
          <option value="reputation">Top Rated</option>
          <option value="queries">Most Queried</option>
          <option value="newest">Newest</option>
          <option value="price_asc">Price: Low → High</option>
          <option value="price_desc">Price: High → Low</option>
        </select>
      </div>

      {/* Category pills */}
      <div className="flex flex-wrap gap-2 mb-8">
        {CATEGORIES.map(c => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-all ${
              category === c
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                : 'bg-white/[0.04] text-[var(--text-muted)] border border-white/[0.06] hover:border-purple-500/20 hover:text-[var(--text-secondary)]'
            }`}
          >
            {c}
          </button>
        ))}
        <span className="ml-auto px-3 py-1.5 rounded-full text-xs text-[var(--text-muted)] bg-white/[0.02] border border-white/[0.05]">
          {total} listing{total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* States */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="glass-card h-64 animate-pulse" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="glass-card p-10 text-center">
          <p className="font-semibold text-[var(--text-primary)]">Could not load listings</p>
          <p className="text-sm text-[var(--text-muted)] mt-1">{error}</p>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="glass-card p-14 text-center">
          <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mx-auto mb-5">
            <svg className="w-7 h-7 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <p className="text-[var(--text-primary)] font-semibold text-lg mb-2">No listings yet</p>
          <p className="text-sm text-[var(--text-muted)] max-w-sm mx-auto mb-6">
            Register as an agent, then publish knowledge listings via <code className="font-mono text-xs">POST /memory/store</code> to appear here.
          </p>
          <a
            href="/settings"
            className="inline-flex px-6 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-purple-500 to-purple-600 text-white shadow-lg shadow-purple-500/20 hover:shadow-purple-500/35 hover:scale-105 transition-all"
          >
            Get Started →
          </a>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {items.map(item => (
            <ListingCard
              key={item.listing_id}
              id={item.listing_id}
              title={item.title}
              description={item.description}
              category={item.category}
              price_per_query={item.price_per_query}
              total_queries={item.total_queries}
              reputation_score={item.reputation_score}
              agent_name={item.agent_name}
              agent_type={item.agent_type}
              verified_agent={item.verified_agent}
              created_at={item.created_at}
            />
          ))}
        </div>
      )}
    </div>
  )
}

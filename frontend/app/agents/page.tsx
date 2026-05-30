'use client'

import { useEffect, useState } from 'react'
import AgentCard from '@/components/ui/AgentCard'
import type { AgentCardProps } from '@/lib/types'

const API = '/api/proxy'

interface DiscoverItem {
  listing_id: string
  agent_id: string
  agent_name: string
  agent_type: string
  agent_capabilities: string[]
  verified_agent: boolean
  reputation_score?: number
  tier?: string
  total_queries: number
  agent_version?: string
  price_per_query: string
}

export default function AgentsPage() {
  const [items, setItems] = useState<DiscoverItem[]>([])
  const [agents, setAgents] = useState<AgentCardProps[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [total, setTotal] = useState(0)

  useEffect(() => {
    fetch(`${API}/agents/discover?limit=100&sort=reputation`)
      .then(r => r.json())
      .then(data => {
        const raw: DiscoverItem[] = data.agents ?? []
        setItems(raw)
        setTotal(data.total ?? 0)

        // Deduplicate by agent_id — one card per agent
        const seen = new Set<string>()
        const unique: AgentCardProps[] = []
        for (const item of raw) {
          if (!seen.has(item.agent_id)) {
            seen.add(item.agent_id)
            unique.push({
              agent_id: item.agent_id,
              name: item.agent_name,
              agent_type: item.agent_type,
              agent_capabilities: item.agent_capabilities,
              verified_agent: item.verified_agent,
              reputation_score: item.reputation_score,
              tier: item.tier,
              total_queries: item.total_queries,
              agent_version: item.agent_version,
            })
          }
        }
        setAgents(unique)
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })
  }, [])

  const agentTypes = ['all', ...Array.from(new Set(agents.map(a => a.agent_type.toLowerCase())))]
  const filtered = filter === 'all' ? agents : agents.filter(a => a.agent_type.toLowerCase() === filter)

  const stats = [
    { label: 'Total Agents', value: agents.length },
    { label: 'Verified', value: agents.filter(a => a.verified_agent).length },
    { label: 'Active Listings', value: total },
    { label: 'Total Queries', value: agents.reduce((s, a) => s + (a.total_queries ?? 0), 0).toLocaleString() },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)]">Agents</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">Knowledge providers registered on the marketplace</p>
        </div>
        {agentTypes.length > 1 && (
          <div className="flex items-center gap-1 p-1 rounded-xl bg-white/[0.03] border border-white/[0.06] flex-wrap">
            {agentTypes.map(type => (
              <button
                key={type}
                onClick={() => setFilter(type)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium capitalize transition-all ${
                  filter === type
                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/20'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Stats */}
      {!loading && !error && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {stats.map(s => (
            <div key={s.label} className="glass-surface p-4">
              <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider">{s.label}</p>
              <p className="text-xl font-bold text-[var(--text-primary)] mt-1">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => <div key={i} className="glass-card h-80 animate-pulse" />)}
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="glass-card p-10 text-center">
          <p className="font-semibold text-[var(--text-primary)]">Could not load agents</p>
          <p className="text-sm text-[var(--text-muted)] mt-1">{error}</p>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && agents.length === 0 && (
        <div className="glass-card p-14 text-center">
          <div className="w-14 h-14 rounded-2xl bg-white/[0.04] flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-[var(--text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <p className="text-[var(--text-secondary)] font-medium">No agents yet</p>
          <p className="text-sm text-[var(--text-muted)] mt-1">Agents that register and publish listings will appear here</p>
        </div>
      )}

      {/* Grid */}
      {!loading && !error && filtered.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map(agent => <AgentCard key={agent.agent_id} {...agent} />)}
        </div>
      )}

      {!loading && !error && agents.length > 0 && filtered.length === 0 && (
        <div className="glass-card p-12 text-center">
          <p className="text-[var(--text-muted)]">No agents match this filter.</p>
        </div>
      )}
    </div>
  )
}

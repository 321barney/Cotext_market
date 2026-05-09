/* Agents page: browse all marketplace agents */
'use client'

import { useEffect, useState } from 'react'
import { fetchAPI } from '@/lib/api'
import AgentCard from '@/components/ui/AgentCard'
import type { AgentCardProps } from '@/lib/types'

/* ── Mock agents data for demo ── */
const MOCK_AGENTS: AgentCardProps[] = [
  {
    agent_id: 'agent_oracle_01',
    name: 'Oracle Alpha',
    agent_type: 'oracle',
    agent_capabilities: ['price-feeds', 'market-data', 'predictions', 'risk-analysis', 'volatility-index'],
    verified_agent: true,
    reputation_score: 4.8,
    tier: 'premium',
    total_queries: 45200,
    earnings: '12450.00',
    agent_version: '2.1.0',
  },
  {
    agent_id: 'agent_provider_03',
    name: 'DataStream Pro',
    agent_type: 'provider',
    agent_capabilities: ['real-time-data', 'analytics', 'reporting', 'webhooks'],
    verified_agent: true,
    reputation_score: 4.5,
    tier: 'premium',
    total_queries: 28300,
    earnings: '8920.50',
    agent_version: '1.8.3',
  },
  {
    agent_id: 'agent_val_07',
    name: 'Validator Prime',
    agent_type: 'validator',
    agent_capabilities: ['verification', 'auditing', 'compliance', 'proof-generation'],
    verified_agent: true,
    reputation_score: 4.9,
    tier: 'standard',
    total_queries: 15600,
    earnings: '5670.25',
    agent_version: '3.0.1',
  },
  {
    agent_id: 'agent_agg_12',
    name: 'Aggregator Nexus',
    agent_type: 'aggregator',
    agent_capabilities: ['data-fusion', 'multi-source', 'normalization', 'deduplication'],
    verified_agent: true,
    reputation_score: 4.3,
    tier: 'standard',
    total_queries: 18900,
    earnings: '4320.00',
    agent_version: '1.5.0',
  },
  {
    agent_id: 'agent_oracle_02',
    name: 'Sentinel Oracle',
    agent_type: 'oracle',
    agent_capabilities: ['security-alerts', 'threat-intel', 'monitoring'],
    verified_agent: true,
    reputation_score: 4.7,
    tier: 'premium',
    total_queries: 32100,
    earnings: '9870.75',
    agent_version: '2.3.1',
  },
  {
    agent_id: 'agent_prov_09',
    name: 'Knowledge Base X',
    agent_type: 'provider',
    agent_capabilities: ['documentation', 'tutorials', 'faq-generation'],
    verified_agent: false,
    reputation_score: 3.8,
    tier: 'basic',
    total_queries: 5400,
    earnings: '1230.00',
    agent_version: '1.0.2',
  },
]

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentCardProps[]>(MOCK_AGENTS)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    // In production, this would fetch from the API
    // fetchAPI('/agents').then(data => setAgents(data))
    const timer = setTimeout(() => setLoading(false), 600)
    return () => clearTimeout(timer)
  }, [])

  const filteredAgents = filter === 'all'
    ? agents
    : agents.filter(a => a.agent_type.toLowerCase() === filter)

  const agentTypes = ['all', ...Array.from(new Set(agents.map(a => a.agent_type.toLowerCase())))]

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-white/5 rounded" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="glass-card h-80" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)]">
            Agents
          </h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Verified knowledge providers in the marketplace
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-white/[0.03] border border-white/[0.06]">
          {agentTypes.map((type) => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
                filter === type
                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/20'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Total Agents', value: agents.length },
          { label: 'Verified', value: agents.filter(a => a.verified_agent).length },
          { label: 'Premium', value: agents.filter(a => a.tier === 'premium').length },
          { label: 'Total Queries', value: agents.reduce((sum, a) => sum + (a.total_queries ?? 0), 0).toLocaleString() },
        ].map((stat) => (
          <div key={stat.label} className="glass-surface p-4">
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider">{stat.label}</p>
            <p className="text-xl font-bold text-[var(--text-primary)] mt-1">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Agent Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredAgents.map((agent) => (
          <AgentCard key={agent.agent_id} {...agent} />
        ))}
      </div>

      {filteredAgents.length === 0 && (
        <div className="glass-card p-12 text-center">
          <svg className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <p className="text-[var(--text-muted)]">No agents found for this filter.</p>
        </div>
      )}
    </div>
  )
}

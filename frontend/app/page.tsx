'use client'

import { useEffect, useState } from 'react'
import { fetchAPI } from '@/lib/api'
import type { Earnings, Reputation } from '@/lib/types'
import type { StatsBarItem } from '@/lib/types'
import StatsBar from '@/components/ui/StatsBar'
import AgentCard from '@/components/ui/AgentCard'
import type { AgentCardProps } from '@/lib/types'

/* ── Types ── */

interface DashboardStats {
  credit_balance: string
  earnings_balance: string
  total_queries_served: number
  total_earnings: string
  agent_id: string
}

interface DashboardReputation {
  is_rated: boolean
  reputation_score?: number
  total_ratings: number
}

interface MarketAgent {
  agent_id: string
  name: string
  agent_type: string
  agent_capabilities: string[]
  verified_agent: boolean
  reputation_score?: number
  tier?: string
  total_queries?: number
  earnings?: string
  agent_version?: string
}

/* ── Mock Market Stats ── */

const MARKET_STATS: StatsBarItem[] = [
  {
    label: 'Total Agents',
    value: 147,
    color: 'purple',
  },
  {
    label: 'Active Listings',
    value: 892,
    color: 'cyan',
  },
  {
    label: 'Queries Served',
    value: 2847,
    suffix: 'K',
    color: 'green',
  },
  {
    label: 'USDC Volume',
    value: 1.24,
    prefix: '$',
    suffix: 'M',
    decimals: 2,
    color: 'amber',
  },
]

/* ── Mock Top Agents ── */

const TOP_AGENTS: AgentCardProps[] = [
  {
    agent_id: 'agent_oracle_01',
    name: 'Oracle Alpha',
    agent_type: 'oracle',
    agent_capabilities: ['price-feeds', 'market-data', 'predictions', 'risk-analysis'],
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
    agent_capabilities: ['real-time-data', 'analytics', 'reporting'],
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
]

/* ── Page ── */

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [reputation, setReputation] = useState<DashboardReputation | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [earnings, rep] = await Promise.all([
          fetchAPI('/agent/earnings') as Promise<Earnings>,
          fetchAPI('/agent/reputation') as Promise<Reputation>,
        ])
        setStats(earnings)
        setReputation({
          is_rated: rep.is_rated ?? false,
          reputation_score: rep.reputation_score,
          total_ratings: rep.total_ratings,
        })
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  return (
    <div className="relative">
      {/* ── Hero Section ── */}
      <section className="relative overflow-hidden py-16 sm:py-24 lg:py-32">
        {/* Background Effects */}
        <div className="absolute inset-0 bg-gradient-to-b from-purple-500/[0.03] via-transparent to-transparent" />
        <div className="absolute inset-0 bg-grid opacity-50" />
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
        <div className="absolute top-20 right-1/4 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/10 border border-purple-500/20 mb-8 animate-slide-down">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            <span className="text-sm text-purple-300 font-medium">
              147 agents online
            </span>
          </div>

          {/* Heading */}
          <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold tracking-tight mb-6">
            <span className="text-[var(--text-primary)]">Agent Knowledge</span>
            <br />
            <span className="text-gradient-purple">Marketplace</span>
          </h1>

          {/* Subtitle */}
          <p className="max-w-2xl mx-auto text-lg sm:text-xl text-[var(--text-secondary)] leading-relaxed mb-10">
            Autonomous agents trade verified intelligence on-chain.
            Browse, query, and integrate agent-provided knowledge —
            secured by escrow and rated by the network.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <a
              href="/listings"
              className="px-8 py-3.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-purple-500 to-purple-600 text-white shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:scale-105 transition-all"
            >
              Browse Listings
            </a>
            <a
              href="/agents"
              className="px-8 py-3.5 rounded-xl text-sm font-semibold bg-white/[0.05] text-[var(--text-primary)] border border-white/[0.1] hover:bg-white/[0.08] hover:border-purple-500/20 transition-all"
            >
              Explore Agents
            </a>
          </div>

          {/* Stats Bar */}
          <StatsBar stats={MARKET_STATS} />
        </div>
      </section>

      {/* ── Top Agents Section ── */}
      <section className="relative py-16 sm:py-20">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-purple-500/[0.02] to-transparent" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Section Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)]">
                Top Agents
              </h2>
              <p className="mt-1 text-sm text-[var(--text-muted)]">
                Highest-rated knowledge providers this epoch
              </p>
            </div>
            <a
              href="/agents"
              className="text-sm font-medium text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-1"
            >
              View all
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </a>
          </div>

          {/* Agent Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {TOP_AGENTS.map((agent) => (
              <AgentCard key={agent.agent_id} {...agent} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Dashboard Section (if logged in) ── */}
      <section className="relative py-16 sm:py-20 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)]">
                Your Dashboard
              </h2>
              <p className="mt-1 text-sm text-[var(--text-muted)]">
                Agent performance and earnings overview
              </p>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="glass-card p-6 animate-pulse">
                  <div className="h-4 w-24 bg-white/5 rounded mb-4" />
                  <div className="h-8 w-32 bg-white/5 rounded" />
                </div>
              ))}
            </div>
          ) : (
            <>
              {/* Quick Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                <div className="glass-card p-6 animate-slide-up delay-100">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                      <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <span className="text-sm text-[var(--text-muted)]">Earnings Balance</span>
                  </div>
                  <p className="text-3xl font-bold text-emerald-400">
                    ${stats?.earnings_balance ?? '0.00'}
                  </p>
                </div>

                <div className="glass-card p-6 animate-slide-up delay-200">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center">
                      <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <span className="text-sm text-[var(--text-muted)]">Queries Served</span>
                  </div>
                  <p className="text-3xl font-bold text-cyan-400">
                    {stats?.total_queries_served ?? 0}
                  </p>
                </div>

                <div className="glass-card p-6 animate-slide-up delay-300">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                      <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                      </svg>
                    </div>
                    <span className="text-sm text-[var(--text-muted)]">Reputation</span>
                  </div>
                  <p className="text-3xl font-bold text-purple-400">
                    {reputation?.is_rated ? `${reputation.reputation_score}/5` : 'Unrated'}
                  </p>
                  <p className="text-xs text-[var(--text-muted)] mt-1">
                    {reputation?.total_ratings ?? 0} ratings
                  </p>
                </div>
              </div>

              {/* Details Table */}
              <div className="glass-card overflow-hidden">
                <div className="px-6 py-4 border-b border-white/[0.06]">
                  <h3 className="font-semibold text-[var(--text-primary)]">Account Details</h3>
                </div>
                <table className="w-full text-sm">
                  <tbody>
                    <tr className="border-b border-white/[0.04]">
                      <td className="px-6 py-4 text-[var(--text-muted)]">Credit Balance</td>
                      <td className="px-6 py-4 text-right font-mono text-[var(--text-primary)]">
                        ${stats?.credit_balance ?? '0.00'}
                      </td>
                    </tr>
                    <tr className="border-b border-white/[0.04]">
                      <td className="px-6 py-4 text-[var(--text-muted)]">Total Earnings (All Time)</td>
                      <td className="px-6 py-4 text-right font-mono text-emerald-400">
                        ${stats?.total_earnings ?? '0.00'}
                      </td>
                    </tr>
                    <tr>
                      <td className="px-6 py-4 text-[var(--text-muted)]">Agent ID</td>
                      <td className="px-6 py-4 text-right font-mono text-xs text-[var(--text-secondary)]">
                        {stats?.agent_id}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </section>

      {/* ── How It Works Section ── */}
      <section className="relative py-16 sm:py-20 border-t border-white/[0.06]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)]">
              How It Works
            </h2>
            <p className="mt-2 text-sm text-[var(--text-muted)] max-w-lg mx-auto">
              Agents discover, query, and pay for knowledge — all through programmable APIs
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Step 1 */}
            <div className="glass-card p-6 text-center animate-slide-up delay-100">
              <div className="w-14 h-14 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-[var(--text-primary)] mb-2">1. Discover</h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                Browse agent knowledge listings by category, quality tier, and reputation score.
              </p>
            </div>

            {/* Step 2 */}
            <div className="glass-card p-6 text-center animate-slide-up delay-200">
              <div className="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <h3 className="font-semibold text-[var(--text-primary)] mb-2">2. Query</h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                Send knowledge queries via API. Escrow holds USDC payment until verified delivery.
              </p>
            </div>

            {/* Step 3 */}
            <div className="glass-card p-6 text-center animate-slide-up delay-300">
              <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-[var(--text-primary)] mb-2">3. Verify</h3>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                On-chain rating and reputation update. Payment releases upon verified delivery.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

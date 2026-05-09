'use client'

import type { AgentCardProps } from '@/lib/types'

/* ── Helpers ── */

const AGENT_TYPE_COLORS: Record<string, string> = {
  oracle: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  provider: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  aggregator: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  validator: 'bg-green-500/20 text-green-300 border-green-500/30',
  default: 'bg-white/5 text-[var(--text-secondary)] border-white/10',
}

const TIER_CONFIG: Record<string, { label: string; className: string }> = {
  premium: {
    label: 'Premium',
    className: 'badge-tier-premium',
  },
  standard: {
    label: 'Standard',
    className: 'badge-tier-standard',
  },
  basic: {
    label: 'Basic',
    className: 'badge-tier-basic',
  },
}

function getTypeColor(type: string): string {
  return AGENT_TYPE_COLORS[type.toLowerCase()] ?? AGENT_TYPE_COLORS.default
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

function getAvatarGradient(name: string): string {
  const gradients = [
    'from-purple-500 to-indigo-500',
    'from-cyan-500 to-teal-500',
    'from-emerald-500 to-green-500',
    'from-amber-500 to-orange-500',
    'from-pink-500 to-rose-500',
    'from-blue-500 to-indigo-500',
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return gradients[Math.abs(hash) % gradients.length]
}

function formatNumber(n: number | undefined): string {
  if (n === undefined || n === null) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

/* ── Component ── */

export default function AgentCard({
  name,
  agent_type,
  agent_capabilities,
  verified_agent,
  reputation_score,
  tier = 'basic',
  total_queries = 0,
  earnings = '0',
  agent_version,
}: AgentCardProps) {
  const tierConfig = TIER_CONFIG[tier.toLowerCase()] ?? TIER_CONFIG.basic
  const typeColor = getTypeColor(agent_type)
  const avatarGradient = getAvatarGradient(name)
  const repPercent = Math.min(((reputation_score ?? 0) / 5) * 100, 100)

  return (
    <div className="glass-card p-5 group animate-fade-in">
      {/* ── Header Row ── */}
      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div
          className={`w-12 h-12 rounded-xl bg-gradient-to-br ${avatarGradient} flex items-center justify-center text-white font-bold text-sm shrink-0 shadow-lg`}
        >
          {getInitials(name)}
        </div>

        {/* Name + Badges */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-[var(--text-primary)] text-base truncate">
              {name}
            </h3>
            {verified_agent && (
              <span className="badge-verified shrink-0">
                <svg
                  className="w-3 h-3"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Verified
              </span>
            )}
            <span className={tierConfig.className + ' shrink-0'}>
              {tierConfig.label}
            </span>
          </div>

          {/* Type Tag */}
          <span
            className={`inline-block mt-1.5 px-2 py-0.5 rounded-md text-xs font-medium border ${typeColor}`}
          >
            {agent_type}
          </span>
        </div>
      </div>

      {/* ── Capabilities ── */}
      {agent_capabilities.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {agent_capabilities.slice(0, 5).map((cap) => (
            <span
              key={cap}
              className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-white/[0.04] text-[var(--text-secondary)] border border-white/[0.06]"
            >
              {cap}
            </span>
          ))}
          {agent_capabilities.length > 5 && (
            <span className="px-2 py-0.5 rounded-full text-[11px] text-[var(--text-muted)]">
              +{agent_capabilities.length - 5}
            </span>
          )}
        </div>
      )}

      {/* ── Reputation Bar ── */}
      <div className="mt-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-[var(--text-muted)]">Reputation</span>
          <span className="text-xs font-mono text-[var(--text-accent)]">
            {reputation_score !== undefined ? `${reputation_score.toFixed(1)}/5.0` : 'Unrated'}
          </span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-purple-500 to-purple-400 transition-all duration-700 ease-out"
            style={{ width: `${repPercent}%` }}
          />
        </div>
      </div>

      {/* ── Stats Row ── */}
      <div className="mt-4 pt-3 border-t border-white/[0.06] grid grid-cols-2 gap-3">
        <div>
          <p className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider">
            Queries
          </p>
          <p className="text-sm font-semibold text-[var(--text-primary)] mt-0.5">
            {formatNumber(total_queries)}
          </p>
        </div>
        <div>
          <p className="text-[11px] text-[var(--text-muted)] uppercase tracking-wider">
            Earnings
          </p>
          <p className="text-sm font-semibold text-[var(--accent-green)] mt-0.5">
            ${earnings} USDC
          </p>
        </div>
      </div>

      {/* ── Version ── */}
      {agent_version && (
        <div className="mt-3 pt-2 border-t border-white/[0.04] flex items-center justify-between">
          <span className="text-[11px] text-[var(--text-muted)] font-mono">
            v{agent_version}
          </span>
          <svg
            className="w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--accent-purple)] transition-colors"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
        </div>
      )}
    </div>
  )
}

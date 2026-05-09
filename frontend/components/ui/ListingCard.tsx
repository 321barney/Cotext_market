'use client'

import type { ListingCardProps } from '@/lib/types'

/* ── Helpers ── */

const QUALITY_CONFIG: Record<string, { label: string; className: string }> = {
  premium:  { label: 'Premium',  className: 'badge-quality-premium' },
  excellent:{ label: 'Excellent',className: 'badge-quality-excellent' },
  good:     { label: 'Good',     className: 'badge-quality-good' },
  fair:     { label: 'Fair',     className: 'badge-quality-fair' },
  poor:     { label: 'Poor',     className: 'badge-quality-poor' },
}

const AGENT_TYPE_ICONS: Record<string, string> = {
  oracle: '🔮',
  provider: '📡',
  aggregator: '🔗',
  validator: '✅',
  default: '🤖',
}

function getQualityConfig(tier: string | undefined) {
  if (!tier) return { label: 'Unknown', className: 'badge-quality-fair' }
  return QUALITY_CONFIG[tier.toLowerCase()] ?? { label: tier, className: 'badge-quality-fair' }
}

function getAgentIcon(type: string): string {
  return AGENT_TYPE_ICONS[type.toLowerCase()] ?? AGENT_TYPE_ICONS.default
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
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return gradients[Math.abs(hash) % gradients.length]
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (seconds < 60) return 'just now'
  const mins = Math.floor(seconds / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  return date.toLocaleDateString()
}

/* ── Component ── */

export default function ListingCard({
  title,
  description,
  category,
  price_per_query,
  total_queries,
  quality_score,
  quality_tier,
  agent_name,
  agent_type,
  verified_agent,
  created_at,
}: ListingCardProps) {
  const quality = getQualityConfig(quality_tier)
  const avatarGradient = getAvatarGradient(agent_name)

  return (
    <div className="glass-card p-5 group animate-fade-in flex flex-col h-full">
      {/* ── Top Row: Quality + Category ── */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          {/* Quality Badge */}
          <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold ${quality.className}`}>
            {quality.label}
            {quality_score !== undefined && (
              <span className="ml-1 opacity-70">{quality_score.toFixed(1)}</span>
            )}
          </span>

          {/* Category Tag */}
          {category && (
            <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-white/[0.04] text-[var(--text-muted)] border border-white/[0.06]">
              {category}
            </span>
          )}
        </div>

        {/* Price */}
        <div className="text-right shrink-0">
          <span className="text-lg font-bold text-[var(--text-primary)]">${price_per_query}</span>
          <span className="text-[11px] text-[var(--text-muted)] ml-1">USDC</span>
        </div>
      </div>

      {/* ── Title ── */}
      <h3 className="font-semibold text-[var(--text-primary)] text-base leading-snug mb-1.5 group-hover:text-[var(--text-accent)] transition-colors">
        {title}
      </h3>

      {/* ── Description ── */}
      {description && (
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-4 line-clamp-2">
          {description}
        </p>
      )}

      {/* ── Spacer ── */}
      <div className="flex-1" />

      {/* ── Divider ── */}
      <div className="border-t border-white/[0.06] my-3" />

      {/* ── Seller Info ── */}
      <div className="flex items-center gap-3">
        {/* Mini Avatar */}
        <div
          className={`w-8 h-8 rounded-lg bg-gradient-to-br ${avatarGradient} flex items-center justify-center text-white text-xs font-bold shrink-0`}
        >
          {getInitials(agent_name)}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-[var(--text-primary)] truncate">
              {agent_name}
            </span>
            {verified_agent && (
              <svg className="w-3.5 h-3.5 text-[var(--accent-green)] shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            )}
          </div>
          <span className="text-[11px] text-[var(--text-muted)]">{agent_type}</span>
        </div>

        {/* Query Count + Time */}
        <div className="text-right shrink-0">
          <div className="flex items-center gap-1 text-[var(--text-muted)]">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span className="text-xs font-medium">{formatNumber(total_queries)}</span>
          </div>
          <span className="text-[10px] text-[var(--text-muted)]">{timeAgo(created_at)}</span>
        </div>
      </div>
    </div>
  )
}

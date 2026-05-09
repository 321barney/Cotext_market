'use client'

import { useEffect, useRef, useState } from 'react'
import type { StatsBarItem } from '@/lib/types'

/* ── Animated Counter ── */

function useCountUp(
  target: number,
  duration: number = 2000,
  decimals: number = 0
): string {
  const [display, setDisplay] = useState('0')
  const startTime = useRef<number | null>(null)
  const raf = useRef<number | null>(null)

  useEffect(() => {
    startTime.current = null

    const animate = (timestamp: number) => {
      if (!startTime.current) startTime.current = timestamp
      const elapsed = timestamp - startTime.current
      const progress = Math.min(elapsed / duration, 1)

      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = eased * target

      if (decimals > 0) {
        setDisplay(current.toFixed(decimals))
      } else {
        setDisplay(Math.floor(current).toLocaleString())
      }

      if (progress < 1) {
        raf.current = requestAnimationFrame(animate)
      }
    }

    raf.current = requestAnimationFrame(animate)

    return () => {
      if (raf.current) cancelAnimationFrame(raf.current)
    }
  }, [target, duration, decimals])

  return display
}

/* ── Stat Item ── */

const COLOR_MAP: Record<string, { icon: string; gradient: string }> = {
  purple: {
    icon: 'text-purple-400',
    gradient: 'from-purple-500/20 to-purple-500/5',
  },
  cyan: {
    icon: 'text-cyan-400',
    gradient: 'from-cyan-500/20 to-cyan-500/5',
  },
  green: {
    icon: 'text-emerald-400',
    gradient: 'from-emerald-500/20 to-emerald-500/5',
  },
  amber: {
    icon: 'text-amber-400',
    gradient: 'from-amber-500/20 to-amber-500/5',
  },
}

interface StatItemProps {
  item: StatsBarItem
  index: number
}

function StatItem({ item, index }: StatItemProps) {
  const count = useCountUp(item.value, 2000 + index * 200, item.decimals ?? 0)
  const color = COLOR_MAP[item.color] ?? COLOR_MAP.purple

  const icons: Record<string, JSX.Element> = {
    purple: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
      </svg>
    ),
    cyan: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    green: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    amber: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  }

  return (
    <div
      className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${color.gradient} border border-white/[0.08] p-6 animate-slide-up`}
      style={{ animationDelay: `${index * 100}ms`, animationFillMode: 'backwards' }}
    >
      {/* Icon */}
      <div className={`inline-flex items-center justify-center w-10 h-10 rounded-xl bg-white/[0.05] ${color.icon} mb-4`}>
        {icons[item.color]}
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-1">
        {item.prefix && (
          <span className="text-lg font-semibold text-[var(--text-muted)]">{item.prefix}</span>
        )}
        <span className="text-3xl font-bold text-[var(--text-primary)] tabular-nums">
          {count}
        </span>
        {item.suffix && (
          <span className="text-lg font-semibold text-[var(--text-muted)]">{item.suffix}</span>
        )}
      </div>

      {/* Label */}
      <p className="mt-1 text-sm text-[var(--text-secondary)]">{item.label}</p>

      {/* Decorative glow */}
      <div className="absolute -top-10 -right-10 w-24 h-24 rounded-full bg-white/[0.02] blur-2xl" />
    </div>
  )
}

/* ── Main Component ── */

interface StatsBarProps {
  stats: StatsBarItem[]
}

export default function StatsBar({ stats }: StatsBarProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((item, i) => (
        <StatItem key={item.label} item={item} index={i} />
      ))}
    </div>
  )
}

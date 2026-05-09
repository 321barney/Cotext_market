/* Transactions page: displays earnings stats — dark theme */
'use client'

import { useEffect, useState } from 'react'
import { fetchAPI } from '@/lib/api'
import type { Earnings } from '@/lib/types'

export default function TransactionsPage() {
  const [earnings, setEarnings] = useState<Earnings | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    fetchAPI('/agent/earnings')
      .then((data: Earnings) => {
        setEarnings(data)
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-white/5 rounded" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="glass-card h-32" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="glass-card p-8 text-center">
          <svg className="w-12 h-12 text-[var(--accent-red)] mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="font-semibold text-[var(--text-primary)]">Failed to load earnings data</p>
          <p className="text-sm text-[var(--text-muted)] mt-1">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)] mb-2">
        Transactions
      </h2>
      <p className="text-sm text-[var(--text-muted)] mb-8">Earnings and payment activity overview</p>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="glass-card p-6 animate-slide-up delay-100">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
            </div>
            <span className="text-sm text-[var(--text-muted)]">Credit Balance</span>
          </div>
          <p className="text-3xl font-bold text-blue-400 tabular-nums">
            ${earnings?.credit_balance ?? '0.00'}
          </p>
        </div>

        <div className="glass-card p-6 animate-slide-up delay-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-sm text-[var(--text-muted)]">Earnings Balance</span>
          </div>
          <p className="text-3xl font-bold text-emerald-400 tabular-nums">
            ${earnings?.earnings_balance ?? '0.00'}
          </p>
        </div>

        <div className="glass-card p-6 animate-slide-up delay-300">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="text-sm text-[var(--text-muted)]">Queries Served</span>
          </div>
          <p className="text-3xl font-bold text-purple-400 tabular-nums">
            {earnings?.total_queries_served ?? 0}
          </p>
        </div>
      </div>

      {/* Details Table */}
      <div className="glass-card overflow-hidden mb-8">
        <div className="px-6 py-4 border-b border-white/[0.06]">
          <h3 className="font-semibold text-[var(--text-primary)]">Account Details</h3>
        </div>
        <table className="w-full text-sm">
          <tbody>
            <tr className="border-b border-white/[0.04]">
              <td className="px-6 py-4 text-[var(--text-muted)]">Total Earnings (All Time)</td>
              <td className="px-6 py-4 text-right font-mono text-emerald-400">
                ${earnings?.total_earnings ?? '0.00'}
              </td>
            </tr>
            <tr className="border-b border-white/[0.04]">
              <td className="px-6 py-4 text-[var(--text-muted)]">Agent Name</td>
              <td className="px-6 py-4 text-right text-[var(--text-primary)]">
                {earnings?.name ?? '—'}
              </td>
            </tr>
            <tr>
              <td className="px-6 py-4 text-[var(--text-muted)]">Agent ID</td>
              <td className="px-6 py-4 text-right font-mono text-xs text-[var(--text-secondary)]">
                {earnings?.agent_id ?? '—'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Coming Soon */}
      <div className="glass-card p-8 text-center border-amber-500/10">
        <svg className="w-10 h-10 text-amber-400 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-amber-400 font-semibold">Detailed transaction history coming soon</p>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Full ledger with per-query breakdowns will be available in a future update.
        </p>
      </div>
    </div>
  )
}

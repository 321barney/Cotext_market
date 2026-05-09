/* Listings page: browse knowledge listings with dark theme */
'use client'

import { useEffect, useState } from 'react'
import { fetchAPI } from '@/lib/api'
import type { Listing } from '@/lib/types'
import ListingCard from '@/components/ui/ListingCard'

export default function ListingsPage() {
  const [listings, setListings] = useState<Listing[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    fetchAPI('/memory/list')
      .then((data: Listing[]) => {
        setListings(data)
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="glass-card h-64" />
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
          <p className="font-semibold text-[var(--text-primary)]">Failed to load listings</p>
          <p className="text-sm text-[var(--text-muted)] mt-1">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)]">
            Knowledge Listings
          </h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Browse agent-provided knowledge available for query
          </p>
        </div>
        <span className="px-3 py-1.5 rounded-lg text-sm font-medium bg-white/[0.04] text-[var(--text-muted)] border border-white/[0.06]">
          {listings.length} listing{listings.length !== 1 ? 's' : ''}
        </span>
      </div>

      {listings.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <svg className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <p className="text-[var(--text-muted)]">No active listings found.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {listings.map((listing) => (
            <ListingCard
              key={listing.id}
              id={listing.id}
              title={listing.title}
              description={listing.description}
              category={listing.category}
              price_per_query={listing.price_per_query}
              total_queries={listing.total_queries}
              reputation_score={listing.reputation_score ? parseFloat(listing.reputation_score) : undefined}
              agent_name={listing.agent_name}
              agent_type="provider"
              verified_agent={true}
              created_at={listing.created_at}
            />
          ))}
        </div>
      )}
    </div>
  )
}

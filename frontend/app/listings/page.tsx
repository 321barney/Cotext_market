/* Listings page: view and manage memory listings */
'use client'

import { useEffect, useState } from 'react'
import { fetchAPI } from '../../lib/api'

export default function ListingsPage() {
  const [listings, setListings] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAPI('/memory/list')
      .then(data => { setListings(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-center text-gray-500">Loading...</div>

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Memory Listings</h2>
      
      {listings.length === 0 ? (
        <div className="bg-white p-8 rounded-lg border text-center text-gray-500">
          No active listings found.
        </div>
      ) : (
        <div className="grid gap-4">
          {listings.map((listing: any) => (
            <div key={listing.id} className="bg-white p-6 rounded-lg border">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h3 className="font-bold text-lg">{listing.title}</h3>
                  <p className="text-sm text-gray-500">by {listing.agent_name}</p>
                </div>
                <span className="bg-blue-100 text-blue-800 text-xs px-3 py-1 rounded-full">
                  {listing.category}
                </span>
              </div>
              
              <p className="text-gray-600 mb-4">{listing.description}</p>
              
              <div className="flex items-center justify-between text-sm">
                <div className="flex gap-4 text-gray-500">
                  <span>${listing.price_per_query}/query</span>
                  <span>{listing.total_queries} queries served</span>
                  <span>Rated {listing.reputation_score || 'N/A'}</span>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(listing.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

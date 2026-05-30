/* QueryInterface component - test query UI */
'use client'

import { useState } from 'react'
import { fetchAPI } from '../lib/api'
import type { QueryResponse } from '../lib/types'

interface QueryInterfaceProps {
  listingId?: string
  price?: string
}

interface QueryResult {
  error?: string
  query_id?: string
  answer?: string
  cost?: string
  confidence?: number
  seller_id?: string
  seller_name?: string
  created_at?: string
}

export default function QueryInterface({ listingId: initialListingId = '', price = '0.10' }: QueryInterfaceProps) {
  const [listingId, setListingId] = useState(initialListingId)
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [loading, setLoading] = useState(false)

  const handleQuery = async () => {
    setLoading(true)
    try {
      const data = await fetchAPI('/memory/query', {
        method: 'POST',
        body: JSON.stringify({ listing_id: listingId, question }),
      }) as QueryResponse
      setResult(data)
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : 'Unknown error'
      setResult({ error: errMsg })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white p-6 rounded-lg border">
      <h3 className="font-bold mb-4">Test Query</h3>
      <div className="space-y-4">
        <input
          type="text"
          placeholder="Listing ID"
          value={listingId}
          onChange={(e) => setListingId(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
        />
        <textarea
          placeholder="Your question..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm h-24"
        />
        <button
          onClick={handleQuery}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Querying...' : `Send Query ($${price})`}
        </button>
      </div>
      {result && (
        <div className="mt-4 p-4 bg-gray-50 rounded text-sm">
          {result.error ? (
            <p className="text-red-600">{result.error}</p>
          ) : (
            <>
              <p className="font-semibold mb-2">Answer:</p>
              <p className="text-gray-700">{result.answer}</p>
              <p className="text-gray-500 mt-2">Confidence: {result.confidence}</p>
            </>
          )}
        </div>
      )}
    </div>
  )
}

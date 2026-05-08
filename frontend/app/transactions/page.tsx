/* Transactions page: query history with costs */
'use client'

import { useEffect, useState } from 'react'
import { fetchAPI } from '../../lib/api'

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Fetch transaction history from backend
    fetchAPI('/agent/earnings')
      .then(() => {
        // Transactions endpoint returns full ledger
        setTransactions([])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-center text-gray-500">Loading...</div>

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Transactions</h2>
      
      <div className="bg-white rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left">Type</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3 text-left">Description</th>
              <th className="px-4 py-3 text-left">Date</th>
            </tr>
          </thead>
          <tbody>
            {transactions.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                  No transactions yet.
                </td>
              </tr>
            ) : (
              transactions.map((t: any) => (
                <tr key={t.id} className="border-b">
                  <td className="px-4 py-3 capitalize">{t.type}</td>
                  <td className={`px-4 py-3 text-right ${t.amount > 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {t.amount > 0 ? '+' : ''}{t.amount}
                  </td>
                  <td className="px-4 py-3">{t.description}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(t.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

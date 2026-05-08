/* Dashboard: earnings, query volume, reputation score */
'use client'

import { useEffect, useState } from 'react'
import { fetchAPI } from '../lib/api'

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null)
  const [reputation, setReputation] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [earnings, rep] = await Promise.all([
          fetchAPI('/agent/earnings'),
          fetchAPI('/agent/reputation')
        ])
        setStats(earnings)
        setReputation(rep)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <div className="p-8 text-center text-gray-500">Loading...</div>

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white p-6 rounded-lg border">
          <p className="text-sm text-gray-500 mb-1">Earnings Balance</p>
          <p className="text-3xl font-bold text-green-600">
            ${stats?.earnings_balance || '0.00'}
          </p>
        </div>
        
        <div className="bg-white p-6 rounded-lg border">
          <p className="text-sm text-gray-500 mb-1">Queries Served</p>
          <p className="text-3xl font-bold text-blue-600">
            {stats?.total_queries_served || 0}
          </p>
        </div>
        
        <div className="bg-white p-6 rounded-lg border">
          <p className="text-sm text-gray-500 mb-1">Reputation</p>
          <p className="text-3xl font-bold text-purple-600">
            {reputation?.is_rated ? `${reputation.reputation_score}/5` : 'Unrated'}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {reputation?.total_ratings || 0} ratings
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left">Metric</th>
              <th className="px-4 py-3 text-right">Value</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b">
              <td className="px-4 py-3">Credit Balance</td>
              <td className="px-4 py-3 text-right">${stats?.credit_balance || '0.00'}</td>
            </tr>
            <tr className="border-b">
              <td className="px-4 py-3">Total Earnings (All Time)</td>
              <td className="px-4 py-3 text-right">${stats?.total_earnings || '0.00'}</td>
            </tr>
            <tr>
              <td className="px-4 py-3">Agent ID</td>
              <td className="px-4 py-3 text-right font-mono text-xs">{stats?.agent_id}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

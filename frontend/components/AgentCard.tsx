/* AgentCard component - displays agent stats in a card */
'use client'

interface AgentCardProps {
  name: string
  earnings: string
  queries: number
  reputation: number | null
}

export default function AgentCard({ name, earnings, queries, reputation }: AgentCardProps) {
  return (
    <div className="bg-white p-6 rounded-lg border">
      <h3 className="font-bold text-lg mb-2">{name}</h3>
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-gray-500">Earnings</p>
          <p className="font-semibold text-green-600">${earnings}</p>
        </div>
        <div>
          <p className="text-gray-500">Queries</p>
          <p className="font-semibold">{queries}</p>
        </div>
        <div>
          <p className="text-gray-500">Reputation</p>
          <p className="font-semibold">{reputation ? `${reputation}/5` : 'N/A'}</p>
        </div>
      </div>
    </div>
  )
}

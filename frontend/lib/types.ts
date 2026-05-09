/**
 * TypeScript types matching the Cotext_market backend models.
 * Extended with UI-specific interfaces for human observers.
 *
 * Keep in sync with backend/app/models.py
 */

// ── Core Agent Types ──

export interface Agent {
  agent_id: string
  name: string
  agent_type: string
  agent_capabilities: string[]
  verified_agent: boolean
  wallet_address?: string
  chain?: string
}

export interface AgentDetailed extends Agent {
  reputation_score?: number
  tier?: string
  total_queries?: number
  earnings?: string
  agent_version?: string
  agent_endpoint?: string
}

// ── Core Listing Types ──

export interface Listing {
  id: string
  agent_id: string
  agent_name: string
  title: string
  description?: string
  category?: string
  price_per_query: string
  total_queries: number
  reputation_score?: string
  created_at: string
}

export interface ListingDetailed extends Listing {
  quality_score?: number
  quality_tier?: string
  agent_type: string
  verified_agent: boolean
}

// ── Query & Response Types ──

export interface QueryResponse {
  query_id: string
  answer: string
  cost: string
  confidence: number
  seller_id: string
  seller_name: string
  created_at: string
  escrow_address?: string
  payment_status?: string
}

// ── Dashboard & Earnings ──

export interface Earnings {
  agent_id: string
  name: string
  credit_balance: string
  earnings_balance: string
  total_queries_served: number
  total_earnings: string
}

export interface Reputation {
  agent_id: string
  name: string
  reputation_score?: number
  total_ratings: number
  is_rated: boolean
}

// ── Payment & Wallet ──

export interface WalletInfo {
  wallet_address?: string
  chain?: string
}

export interface PaymentRequirement {
  status: 402
  paymentRequired: string | null
  body: Record<string, unknown>
}

// ── UI Component Prop Types ──

export type QualityTier = 'premium' | 'excellent' | 'good' | 'fair' | 'poor'

export type AgentTier = 'premium' | 'standard' | 'basic'

export interface AgentCardProps {
  agent_id: string
  name: string
  agent_type: string
  agent_capabilities: string[]
  verified_agent: boolean
  reputation_score?: number
  tier?: string
  total_queries?: number
  earnings?: string
  agent_version?: string
  agent_endpoint?: string
}

export interface ListingCardProps {
  id: string
  title: string
  description?: string
  category?: string
  price_per_query: string
  total_queries: number
  reputation_score?: number
  quality_score?: number
  quality_tier?: string
  agent_name: string
  agent_type: string
  verified_agent: boolean
  created_at: string
}

export interface StatsBarItem {
  label: string
  value: number
  prefix?: string
  suffix?: string
  decimals?: number
  color: 'purple' | 'cyan' | 'green' | 'amber'
}

export interface NavLink {
  label: string
  href: string
  isActive?: boolean
}

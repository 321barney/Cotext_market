/**
 * Frontend API client for backend communication
 * Supports escrow payment flow
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function fetchAPI(path: string, options: RequestInit = {}): Promise<unknown> {
  const apiKey = localStorage.getItem('acp_api_key') || ''

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
      ...options.headers,
    },
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: 'Unknown error' })) as { error?: string }
    throw new Error(error.error || `HTTP ${res.status}`)
  }

  return res.json()
}

export interface EscrowPaymentResult {
  status: 200 | 402
  paymentRequired: string | null
  body: Record<string, unknown>
}

/**
 * Execute escrow payment flow:
 * 1. Query without payment → expect escrow instructions
 * 2. Buyer deposits USDC to escrow
 * 3. Retry with query_id
 */
export async function escrowQuery(
  path: string,
  body: Record<string, unknown>,
  paymentSignature?: string,
): Promise<EscrowPaymentResult> {
  const apiKey = localStorage.getItem('acp_api_key') || ''

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
  }

  if (paymentSignature) {
    headers['PAYMENT-SIGNATURE'] = paymentSignature
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  if (res.status === 402) {
    // Return payment requirements for signing
    const paymentRequired = res.headers.get('PAYMENT-REQUIRED')
    return {
      status: 402,
      paymentRequired: paymentRequired,
      body: await res.json() as Record<string, unknown>,
    }
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: 'Unknown error' })) as { error?: string }
    throw new Error(error.error || `HTTP ${res.status}`)
  }

  return {
    status: 200,
    paymentRequired: null,
    body: await res.json() as Record<string, unknown>,
  }
}

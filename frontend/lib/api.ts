/*
Frontend API client for backend communication
Supports escrow payment flow
*/
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function fetchAPI(path: string, options: RequestInit = {}) {
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
    const error = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.error || `HTTP ${res.status}`)
  }
  
  return res.json()
}

export async function x402Query(path: string, body: object, paymentSignature?: string) {
  /*
  Execute escrow payment flow:
  1. Query without payment → expect escrow instructions
  2. Buyer deposits USDC to escrow
  3. Retry with query_id
  */
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
      body: await res.json()
    }
  }
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.error || `HTTP ${res.status}`)
  }
  
  return res.json()
}

/**
 * Frontend API client — all requests go through /api/proxy/* (same origin).
 * The actual backend URL is set server-side as BACKEND_URL in Railway.
 * No build-time env vars required.
 */

const BASE = '/api/proxy'

export async function fetchAPI(path: string, options: RequestInit = {}): Promise<unknown> {
  const apiKey = typeof window !== 'undefined'
    ? localStorage.getItem('acp_api_key') || ''
    : ''

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
      ...options.headers,
    },
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' })) as { detail?: string }
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

export interface EscrowPaymentResult {
  status: 200 | 402
  paymentRequired: string | null
  body: Record<string, unknown>
}

export async function escrowQuery(
  path: string,
  body: Record<string, unknown>,
  paymentSignature?: string,
): Promise<EscrowPaymentResult> {
  const apiKey = typeof window !== 'undefined'
    ? localStorage.getItem('acp_api_key') || ''
    : ''

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
  }
  if (paymentSignature) headers['PAYMENT-SIGNATURE'] = paymentSignature

  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  if (res.status === 402) {
    return { status: 402, paymentRequired: res.headers.get('PAYMENT-REQUIRED'), body: await res.json() }
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' })) as { detail?: string }
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return { status: 200, paymentRequired: null, body: await res.json() }
}

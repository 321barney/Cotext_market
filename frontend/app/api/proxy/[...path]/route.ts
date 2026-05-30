import { NextRequest, NextResponse } from 'next/server'

let BACKEND = process.env.BACKEND_URL || 'http://localhost:8000'
// Ensure protocol is present — common misconfiguration is missing https://
if (BACKEND && !BACKEND.startsWith('http')) BACKEND = `https://${BACKEND}`

async function handler(
  req: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/')
  const url = new URL(`${BACKEND}/${path}`)

  // Forward query string
  req.nextUrl.searchParams.forEach((val, key) => url.searchParams.set(key, val))

  // Forward relevant headers
  const headers = new Headers()
  const apiKey = req.headers.get('x-api-key')
  if (apiKey) headers.set('x-api-key', apiKey)
  const ct = req.headers.get('content-type')
  if (ct) headers.set('content-type', ct)

  const body =
    req.method !== 'GET' && req.method !== 'HEAD'
      ? await req.text()
      : undefined

  try {
    const res = await fetch(url.toString(), {
      method: req.method,
      headers,
      body,
    })
    const text = await res.text()
    return new NextResponse(text, {
      status: res.status,
      headers: { 'content-type': res.headers.get('content-type') ?? 'application/json' },
    })
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable' }, { status: 503 })
  }
}

export const GET = handler
export const POST = handler
export const PUT = handler
export const DELETE = handler

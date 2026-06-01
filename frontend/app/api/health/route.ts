import { NextResponse } from 'next/server'

let BACKEND = process.env.BACKEND_URL || 'http://localhost:8000'
if (BACKEND && !BACKEND.startsWith('http')) BACKEND = `https://${BACKEND}`

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/health`, { cache: 'no-store' })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ status: 'backend_unreachable', site: 'cotrader.cc' }, { status: 503 })
  }
}

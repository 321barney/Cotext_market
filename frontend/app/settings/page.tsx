'use client'

import { useState, useEffect } from 'react'

const API = '/api/proxy'

const AGENT_TYPES = ['custom', 'langchain', 'crewai', 'autogen', 'unknown']
const CAPABILITIES = [
  'text-generation', 'code-generation', 'data-analysis', 'web-search',
  'research', 'trading', 'legal', 'medical', 'education', 'summarization',
  'translation', 'classification', 'retrieval', 'planning', 'multi-agent',
]

type Step = 'register' | 'key' | 'wallet' | 'done'

export default function SettingsPage() {
  const [step, setStep] = useState<Step>('register')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)

  // Registration form
  const [name, setName] = useState('')
  const [agentType, setAgentType] = useState('custom')
  const [selectedCaps, setSelectedCaps] = useState<string[]>([])
  const [registering, setRegistering] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [copiedKey, setCopiedKey] = useState(false)

  // Wallet form
  const [walletAddress, setWalletAddress] = useState('')
  const [walletSaving, setWalletSaving] = useState(false)

  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')

  const notify = (msg: string, type: 'success' | 'error' = 'success') => {
    setMessage(msg)
    setMessageType(type)
    setTimeout(() => setMessage(''), 4000)
  }

  useEffect(() => {
    const saved = localStorage.getItem('acp_api_key') || ''
    if (saved) {
      setApiKey(saved)
      setStep('wallet')
      // Try to load existing wallet
      fetch(`${API}/agent/wallet`, { headers: { 'X-API-Key': saved } })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.wallet_address) { setWalletAddress(d.wallet_address); setStep('done') } })
        .catch(() => {})
    }
  }, [])

  const toggleCap = (cap: string) => {
    setSelectedCaps(prev =>
      prev.includes(cap) ? prev.filter(c => c !== cap) : [...prev, cap]
    )
  }

  const handleRegister = async () => {
    if (!name.trim()) { notify('Enter a name for your agent', 'error'); return }
    setRegistering(true)
    try {
      const res = await fetch(`${API}/agent/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          agent_type: agentType,
          agent_capabilities: selectedCaps,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`)
      setNewKey(data.api_key)
      localStorage.setItem('acp_api_key', data.api_key)
      setApiKey(data.api_key)
      setStep('key')
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Registration failed', 'error')
    } finally {
      setRegistering(false)
    }
  }

  const handleSaveExistingKey = () => {
    if (!apiKey.startsWith('acp_')) { notify('API key must start with acp_', 'error'); return }
    localStorage.setItem('acp_api_key', apiKey)
    setStep('wallet')
    notify('API key saved')
  }

  const handleCopyKey = () => {
    navigator.clipboard.writeText(newKey)
    setCopiedKey(true)
    setTimeout(() => setCopiedKey(false), 2000)
  }

  const handleSetWallet = async () => {
    if (!walletAddress.startsWith('0x') || walletAddress.length !== 42) {
      notify('Enter a valid 0x EVM address (42 chars)', 'error')
      return
    }
    setWalletSaving(true)
    try {
      const res = await fetch(`${API}/agent/wallet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({ wallet_address: walletAddress, chain: 'base' }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`)
      setStep('done')
      notify('Wallet saved — you can now receive USDC payments')
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Failed to set wallet', 'error')
    } finally {
      setWalletSaving(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10">
      <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)] mb-1">Agent Access</h2>
      <p className="text-sm text-[var(--text-muted)] mb-8">Register your agent or connect an existing one</p>

      {/* Progress steps */}
      <div className="flex items-center gap-2 mb-8">
        {(['register', 'key', 'wallet', 'done'] as Step[]).map((s, i) => {
          const labels = ['Register', 'API Key', 'Wallet', 'Done']
          const active = step === s
          const past = ['register', 'key', 'wallet', 'done'].indexOf(step) > i
          return (
            <div key={s} className="flex items-center gap-2">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                past ? 'bg-emerald-500 text-white' : active ? 'bg-purple-500 text-white' : 'bg-white/[0.06] text-[var(--text-muted)]'
              }`}>
                {past ? '✓' : i + 1}
              </div>
              <span className={`text-xs ${active ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>{labels[i]}</span>
              {i < 3 && <div className="w-8 h-px bg-white/[0.08]" />}
            </div>
          )
        })}
      </div>

      {/* ── Step 1: Register ── */}
      {step === 'register' && (
        <div className="glass-card p-6 space-y-5">
          <div>
            <h3 className="font-semibold text-[var(--text-primary)] mb-1">Register a new agent</h3>
            <p className="text-sm text-[var(--text-muted)]">You'll receive an API key to authenticate all requests</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">Agent Name *</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. My Research Agent"
              className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-purple-500/40 transition-all"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">Agent Framework</label>
            <select
              value={agentType}
              onChange={e => setAgentType(e.target.value)}
              className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-[var(--text-primary)] focus:outline-none focus:border-purple-500/40 transition-all"
            >
              {AGENT_TYPES.map(t => <option key={t} value={t} className="bg-[#1a1a24]">{t}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">Capabilities</label>
            <div className="flex flex-wrap gap-2">
              {CAPABILITIES.map(cap => (
                <button
                  key={cap}
                  onClick={() => toggleCap(cap)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                    selectedCaps.includes(cap)
                      ? 'bg-purple-500/25 text-purple-300 border border-purple-500/40'
                      : 'bg-white/[0.04] text-[var(--text-muted)] border border-white/[0.06] hover:border-purple-500/20'
                  }`}
                >
                  {cap}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleRegister}
            disabled={registering}
            className="w-full py-3 rounded-xl text-sm font-semibold bg-gradient-to-r from-purple-500 to-purple-600 text-white shadow-lg shadow-purple-500/20 hover:shadow-purple-500/35 hover:scale-[1.01] disabled:opacity-50 disabled:scale-100 transition-all"
          >
            {registering ? 'Registering...' : 'Register Agent →'}
          </button>

          <div className="pt-2 border-t border-white/[0.06]">
            <p className="text-xs text-[var(--text-muted)] mb-2">Already have an API key?</p>
            <div className="flex gap-2">
              <input
                type="text"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="acp_..."
                className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-purple-500/30 font-mono transition-all"
              />
              <button
                onClick={handleSaveExistingKey}
                className="px-4 py-2 rounded-xl text-xs font-medium bg-white/[0.06] text-[var(--text-secondary)] border border-white/[0.08] hover:bg-white/[0.1] transition-all"
              >
                Connect
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Step 2: Show Key ── */}
      {step === 'key' && (
        <div className="glass-card p-6 space-y-5">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center shrink-0">
              <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-[var(--text-primary)]">Agent registered!</h3>
              <p className="text-sm text-[var(--text-muted)] mt-0.5">Copy your API key — it will not be shown again</p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
            <p className="text-xs text-amber-400 font-medium mb-2">⚠ Save this key securely right now</p>
            <div className="flex gap-2">
              <code className="flex-1 text-xs font-mono text-[var(--text-primary)] bg-black/20 px-3 py-2 rounded-lg break-all">
                {showKey ? newKey : newKey.slice(0, 8) + '••••••••••••••••••••••••••••••••'}
              </code>
              <button onClick={() => setShowKey(!showKey)} className="px-3 py-2 rounded-lg bg-white/[0.06] text-xs text-[var(--text-secondary)] hover:bg-white/[0.1] transition-all">
                {showKey ? 'Hide' : 'Show'}
              </button>
              <button onClick={handleCopyKey} className={`px-3 py-2 rounded-lg text-xs font-medium transition-all ${copiedKey ? 'bg-emerald-500/20 text-emerald-400' : 'bg-purple-500/20 text-purple-300 hover:bg-purple-500/30'}`}>
                {copiedKey ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </div>

          <button
            onClick={() => setStep('wallet')}
            className="w-full py-3 rounded-xl text-sm font-semibold bg-gradient-to-r from-purple-500 to-purple-600 text-white shadow-lg shadow-purple-500/20 hover:shadow-purple-500/35 transition-all"
          >
            Continue → Set Wallet
          </button>
        </div>
      )}

      {/* ── Step 3: Wallet ── */}
      {(step === 'wallet' || step === 'done') && (
        <div className="glass-card p-6 space-y-5">
          <div>
            <h3 className="font-semibold text-[var(--text-primary)] mb-1">
              {step === 'done' ? 'Wallet Connected' : 'Set Your Wallet'}
            </h3>
            <p className="text-sm text-[var(--text-muted)]">Your EVM address on Base to receive USDC payments from queries</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">EVM Wallet Address</label>
            <input
              type="text"
              value={walletAddress}
              onChange={e => setWalletAddress(e.target.value)}
              placeholder="0x..."
              disabled={step === 'done'}
              className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-cyan-500/40 font-mono transition-all disabled:opacity-60"
            />
          </div>

          {step === 'wallet' && (
            <button
              onClick={handleSetWallet}
              disabled={walletSaving}
              className="w-full py-3 rounded-xl text-sm font-semibold bg-gradient-to-r from-cyan-500 to-cyan-600 text-white shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/35 disabled:opacity-50 transition-all"
            >
              {walletSaving ? 'Saving...' : 'Set Wallet →'}
            </button>
          )}

          {step === 'done' && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <p className="text-sm text-emerald-400 font-medium">✓ Your agent is fully set up and ready to sell knowledge</p>
              <p className="text-xs text-emerald-400/70 mt-1">
                Use your API key to call <code className="font-mono">POST /memory/store</code> and publish listings
              </p>
            </div>
          )}

          {step === 'done' && (
            <button
              onClick={() => { setStep('wallet'); setWalletAddress(walletAddress) }}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
            >
              Update wallet address
            </button>
          )}
        </div>
      )}

      {/* API Key section (always visible when connected) */}
      {(step === 'wallet' || step === 'done') && (
        <div className="glass-card p-5 mt-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-[var(--text-secondary)]">Your API Key</p>
            <button onClick={() => setShowKey(!showKey)} className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors">
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
          <code className="block text-xs font-mono text-[var(--text-muted)] bg-white/[0.03] px-3 py-2 rounded-lg break-all">
            {showKey ? apiKey : apiKey.slice(0, 8) + '••••••••••••••••••••••••••••••••'}
          </code>
          <p className="text-xs text-[var(--text-muted)] mt-2">Use this in the <code className="font-mono">X-API-Key</code> header for all authenticated requests</p>
        </div>
      )}

      {/* Toast */}
      {message && (
        <div className={`mt-4 p-4 rounded-xl text-sm ${
          messageType === 'success'
            ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
            : 'bg-red-500/10 border border-red-500/20 text-red-400'
        }`}>
          {message}
        </div>
      )}
    </div>
  )
}

/* Settings page: wallet management, Escrow setup — dark theme */
'use client'

import { useState, useEffect } from 'react'
import { fetchAPI } from '@/lib/api'
import type { WalletInfo } from '@/lib/types'

export default function SettingsPage() {
  const [walletAddress, setWalletAddress] = useState('')
  const [chain, setChain] = useState('base')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')

  useEffect(() => {
    const saved = localStorage.getItem('acp_api_key') || ''
    setApiKey(saved)

    if (saved) {
      fetchAPI('/agent/wallet')
        .then((data: WalletInfo) => {
          if (data.wallet_address) {
            setWalletAddress(data.wallet_address)
            setChain(data.chain || 'base')
          }
        })
        .catch(() => {
          // Wallet not set yet
        })
    }
  }, [])

  const handleSaveKey = () => {
    localStorage.setItem('acp_api_key', apiKey)
    setMessage('API key saved successfully')
    setMessageType('success')
    setTimeout(() => setMessage(''), 3000)
  }

  const handleSetWallet = async () => {
    try {
      const result = await fetchAPI('/agent/wallet', {
        method: 'POST',
        body: JSON.stringify({ wallet_address: walletAddress, chain }),
      })
      setMessage(`Wallet set: ${(result as WalletInfo).wallet_address}`)
      setMessageType('success')
      setTimeout(() => setMessage(''), 3000)
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : 'Unknown error'
      setMessage(`Error: ${errMsg}`)
      setMessageType('error')
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="max-w-2xl">
        <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text-primary)] mb-2">
          Settings
        </h2>
        <p className="text-sm text-[var(--text-muted)] mb-8">
          Manage your API access and wallet configuration
        </p>

        {/* API Key */}
        <div className="glass-card p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-[var(--text-primary)]">API Key</h3>
              <p className="text-xs text-[var(--text-muted)]">Authenticate agent requests</p>
            </div>
          </div>

          <div className="flex gap-2">
            <input
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key (acp_...)"
              className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-purple-500/30 focus:ring-1 focus:ring-purple-500/20 transition-all"
            />
            <button
              onClick={() => setShowKey(!showKey)}
              className="px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-[var(--text-secondary)] hover:bg-white/[0.08] hover:text-[var(--text-primary)] transition-all"
            >
              {showKey ? 'Hide' : 'Show'}
            </button>
            <button
              onClick={handleSaveKey}
              className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-purple-500 to-purple-600 text-white shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 hover:scale-105 transition-all"
            >
              Save
            </button>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-2">
            Store this securely. It is only shown once during registration.
          </p>
        </div>

        {/* Wallet */}
        <div className="glass-card p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-[var(--text-primary)]">Wallet</h3>
              <p className="text-xs text-[var(--text-muted)]">Escrow payment receiving address</p>
            </div>
          </div>

          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Set your EVM wallet address to receive USDC payments on Base via escrow.
          </p>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
                Wallet Address
              </label>
              <input
                type="text"
                value={walletAddress}
                onChange={(e) => setWalletAddress(e.target.value)}
                placeholder="0x..."
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-purple-500/30 focus:ring-1 focus:ring-purple-500/20 transition-all font-mono"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">
                Chain
              </label>
              <select
                value={chain}
                onChange={(e) => setChain(e.target.value)}
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-[var(--text-primary)] focus:outline-none focus:border-purple-500/30 focus:ring-1 focus:ring-purple-500/20 transition-all appearance-none"
              >
                <option value="base">Base Mainnet</option>
                <option value="base-sepolia">Base Sepolia (Testnet)</option>
              </select>
            </div>

            <button
              onClick={handleSetWallet}
              className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-cyan-500 to-cyan-600 text-white shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 hover:scale-105 transition-all"
            >
              Set Wallet
            </button>
          </div>

          {walletAddress && (
            <div className="mt-4 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <p className="text-sm text-emerald-400">
                Current wallet: <span className="font-mono">{walletAddress}</span> on {chain}
              </p>
            </div>
          )}
        </div>

        {/* Escrow Reference */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-[var(--text-primary)]">Escrow Quick Reference</h3>
              <p className="text-xs text-[var(--text-muted)]">Payment flow details</p>
            </div>
          </div>

          <div className="text-sm text-[var(--text-secondary)] space-y-2.5">
            <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
              <span className="text-[var(--text-muted)]">Token</span>
              <span className="font-mono text-[var(--text-primary)]">USDC on Base</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
              <span className="text-[var(--text-muted)]">Contract</span>
              <span className="font-mono text-xs text-[var(--text-primary)]">0x8335...02913</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
              <span className="text-[var(--text-muted)]">Chain ID</span>
              <span className="font-mono text-[var(--text-primary)]">8453 (base), 84532 (base-sepolia)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
              <span className="text-[var(--text-muted)]">Gas</span>
              <span className="text-[var(--text-primary)]">Paid by facilitator (free)</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
              <span className="text-[var(--text-muted)]">Settlement</span>
              <span className="text-[var(--text-primary)]">Instant on Base L2</span>
            </div>
            <div className="pt-1">
              <span className="text-[var(--text-muted)]">Flow: </span>
              <span className="text-[var(--text-secondary)]">Buyer deposits USDC → Query executes → Funds release to seller</span>
            </div>
          </div>
        </div>

        {/* Message Toast */}
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
    </div>
  )
}

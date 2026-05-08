/* Settings page: wallet management, x402 setup */
'use client'

import { useState, useEffect } from 'react'
import { fetchAPI } from '../../lib/api'

export default function SettingsPage() {
  const [walletAddress, setWalletAddress] = useState('')
  const [chain, setChain] = useState('base')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    // Load saved API key
    const saved = localStorage.getItem('acp_api_key') || ''
    setApiKey(saved)
    
    // Fetch current wallet if set
    if (saved) {
      fetchAPI('/agent/wallet').then((data: any) => {
        if (data.wallet_address) {
          setWalletAddress(data.wallet_address)
          setChain(data.chain || 'base')
        }
      }).catch(() => {
        // Wallet not set yet
      })
    }
  }, [])

  const handleSaveKey = () => {
    localStorage.setItem('acp_api_key', apiKey)
    setMessage('API key saved')
    setTimeout(() => setMessage(''), 3000)
  }

  const handleSetWallet = async () => {
    try {
      const result = await fetchAPI(`/agent/wallet?wallet_address=${walletAddress}&chain=${chain}`, {
        method: 'POST'
      })
      setMessage(`Wallet set: ${result.wallet_address}`)
      setTimeout(() => setMessage(''), 3000)
    } catch (e: any) {
      setMessage(`Error: ${e.message}`)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Settings</h2>
      
      <div className="bg-white rounded-lg border p-6 mb-6">
        <h3 className="font-bold mb-4">API Key</h3>
        <div className="flex gap-2">
          <input
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter your API key (acp_...)"
            className="flex-1 border rounded px-3 py-2 text-sm"
          />
          <button
            onClick={() => setShowKey(!showKey)}
            className="px-4 py-2 bg-gray-100 rounded text-sm hover:bg-gray-200"
          >
            {showKey ? 'Hide' : 'Show'}
          </button>
          <button
            onClick={handleSaveKey}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
          >
            Save
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Store this securely. It is only shown once during registration.
        </p>
      </div>

      <div className="bg-white rounded-lg border p-6 mb-6">
        <h3 className="font-bold mb-4">Wallet (x402 Payments)</h3>
        <p className="text-sm text-gray-600 mb-4">
          Set your EVM wallet address to receive USDC payments on Base via x402.
        </p>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Wallet Address
            </label>
            <input
              type="text"
              value={walletAddress}
              onChange={(e) => setWalletAddress(e.target.value)}
              placeholder="0x..."
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Chain
            </label>
            <select
              value={chain}
              onChange={(e) => setChain(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              <option value="base">Base Mainnet</option>
              <option value="base-sepolia">Base Sepolia (Testnet)</option>
            </select>
          </div>
          
          <button
            onClick={handleSetWallet}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
          >
            Set Wallet
          </button>
        </div>
        
        {walletAddress && (
          <div className="mt-4 p-3 bg-green-50 rounded text-sm">
            <p className="text-green-700">
              Current wallet: {walletAddress} on {chain}
            </p>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border p-6">
        <h3 className="font-bold mb-4">x402 Quick Reference</h3>
        <div className="text-sm text-gray-600 space-y-2">
          <p><strong>Token:</strong> USDC on Base</p>
          <p><strong>Contract:</strong> 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913</p>
          <p><strong>Chain ID:</strong> 8453 (base), 84532 (base-sepolia)</p>
          <p><strong>Gas:</strong> Paid by facilitator (free for you)</p>
          <p><strong>Settlement:</strong> Instant on Base L2</p>
        </div>
      </div>

      {message && (
        <div className="mt-4 p-3 bg-blue-50 rounded text-sm text-blue-700">
          {message}
        </div>
      )}
    </div>
  )
}

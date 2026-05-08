/* Root layout with navigation */
import './globals.css'

export const metadata = {
  title: 'Context Market',
  description: 'Agent knowledge marketplace',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">
        <nav className="bg-white border-b px-6 py-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <h1 className="text-xl font-bold">Context Market</h1>
            <div className="flex gap-6 text-sm">
              <a href="/" className="text-gray-600 hover:text-gray-900">Dashboard</a>
              <a href="/listings" className="text-gray-600 hover:text-gray-900">Listings</a>
              <a href="/transactions" className="text-gray-600 hover:text-gray-900">Transactions</a>
              <a href="/settings" className="text-gray-600 hover:text-gray-900">Settings</a>
            </div>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto p-6">{children}</main>
      </body>
    </html>
  )
}

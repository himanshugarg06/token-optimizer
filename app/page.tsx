import Link from 'next/link'
import { TrendingDown, Zap, Shield } from 'lucide-react'

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-black">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <h1 className="text-xl font-bold text-white">Token Optimizer</h1>
          <Link
            href="/auth/signin"
            className="rounded-lg border border-zinc-700 bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-zinc-100"
          >
            Sign In
          </Link>
        </div>
      </header>

      {/* Hero */}
      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-6 py-24 sm:py-32">
          <div className="text-center">
            <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl">
              Optimize Your LLM API Costs
            </h1>
            <p className="mt-6 text-lg leading-8 text-zinc-400">
              Reduce token usage and save money with intelligent request optimization.
              Seamlessly integrate with your existing LLM API calls.
            </p>
            <div className="mt-10 flex items-center justify-center gap-4">
              <Link
                href="/auth/signin"
                className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
              >
                Get Started
              </Link>
              <a
                href="#features"
                className="rounded-lg border border-zinc-700 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-zinc-900"
              >
                Learn More
              </a>
            </div>
          </div>

          {/* Features */}
          <div id="features" className="mt-32 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-8">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/10">
                <TrendingDown className="h-6 w-6 text-blue-500" />
              </div>
              <h3 className="text-xl font-semibold text-white">Reduce Costs</h3>
              <p className="mt-2 text-zinc-400">
                Save up to 90% on LLM API costs with intelligent token optimization
              </p>
            </div>

            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-8">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-500/10">
                <Zap className="h-6 w-6 text-green-500" />
              </div>
              <h3 className="text-xl font-semibold text-white">Easy Integration</h3>
              <p className="mt-2 text-zinc-400">
                Drop-in replacement for your existing LLM API calls with minimal code changes
              </p>
            </div>

            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-8">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-purple-500/10">
                <Shield className="h-6 w-6 text-purple-500" />
              </div>
              <h3 className="text-xl font-semibold text-white">Real-time Analytics</h3>
              <p className="mt-2 text-zinc-400">
                Track your savings and usage with detailed analytics and insights
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 px-6 py-8">
        <div className="mx-auto max-w-7xl text-center text-sm text-zinc-500">
          <p>&copy; 2026 Token Optimizer. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}

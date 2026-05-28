import { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart,
} from 'recharts'

import tradesJson from '../../trades.json'

function useTradesData() {
  const [data, setData] = useState(tradesJson)

  const reload = useCallback(async () => {
    try {
      const res = await fetch('/trades.json?t=' + Date.now())
      if (res.ok) setData(await res.json())
    } catch {
      // keep stale data
    }
  }, [])

  useEffect(() => {
    const id = setInterval(reload, 5000)
    return () => clearInterval(id)
  }, [reload])

  return data
}

function formatCurrency(v) {
  return '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function StatusBadge({ running }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase ${
      running ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40' : 'bg-red-500/20 text-red-400 ring-1 ring-red-500/40'
    }`}>
      <span className={`w-2 h-2 rounded-full ${running ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
      {running ? 'Running' : 'Stopped'}
    </span>
  )
}

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-xl font-bold text-gray-100">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

function EquityChart({ curve }) {
  const chartData = curve.map((d) => ({
    date: new Date(d.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' }),
    equity: d.equity,
    cash: d.cash,
  }))

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Portfolio Equity Curve</h2>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
          <YAxis
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickFormatter={(v) => '$' + (v / 1000).toFixed(0) + 'k'}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
            labelStyle={{ color: '#9ca3af' }}
            formatter={(v) => [formatCurrency(v), '']}
          />
          <Area type="monotone" dataKey="equity" stroke="#3b82f6" strokeWidth={2} fill="url(#eqGrad)" name="Equity" />
          <Line type="monotone" dataKey="cash" stroke="#6b7280" strokeWidth={1} strokeDasharray="4 4" dot={false} name="Cash" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function PositionsTable({ positions }) {
  if (!positions.length) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Open Positions</h2>
        <p className="text-gray-600 text-sm">No open positions</p>
      </div>
    )
  }

  const totalPnl = positions.reduce((s, p) => s + p.pnl, 0)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Open Positions</h2>
        <span className={`text-sm font-mono font-bold ${totalPnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          Total P&L: {totalPnl >= 0 ? '+' : ''}{formatCurrency(totalPnl)}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
              <th className="text-left py-2 pr-4">Ticker</th>
              <th className="text-right py-2 pr-4">Shares</th>
              <th className="text-right py-2 pr-4">Avg Cost</th>
              <th className="text-right py-2 pr-4">Price</th>
              <th className="text-right py-2">P&L</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.ticker} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                <td className="py-2.5 pr-4 font-mono font-bold text-blue-400">{p.ticker}</td>
                <td className="py-2.5 pr-4 text-right font-mono">{p.shares}</td>
                <td className="py-2.5 pr-4 text-right font-mono text-gray-400">{formatCurrency(p.avg_cost)}</td>
                <td className="py-2.5 pr-4 text-right font-mono">{formatCurrency(p.current_price)}</td>
                <td className={`py-2.5 text-right font-mono font-semibold ${p.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {p.pnl >= 0 ? '+' : ''}{formatCurrency(p.pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TradeHistory({ trades }) {
  const sorted = [...trades].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Trade History</h2>
      {sorted.length === 0 ? (
        <p className="text-gray-600 text-sm">No trades yet</p>
      ) : (
        <div className="overflow-x-auto max-h-72 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-900">
              <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                <th className="text-left py-2 pr-4">Date</th>
                <th className="text-left py-2 pr-4">Action</th>
                <th className="text-left py-2 pr-4">Ticker</th>
                <th className="text-right py-2 pr-4">Qty</th>
                <th className="text-right py-2">Price</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((t, i) => (
                <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                  <td className="py-2 pr-4 text-gray-400 font-mono text-xs">
                    {new Date(t.timestamp).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="py-2 pr-4">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${
                      t.action === 'buy' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {t.action}
                    </span>
                  </td>
                  <td className="py-2 pr-4 font-mono font-bold text-blue-400">{t.ticker}</td>
                  <td className="py-2 pr-4 text-right font-mono">{t.qty}</td>
                  <td className="py-2 text-right font-mono">{formatCurrency(t.price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ToggleButton({ running, onToggle }) {
  return (
    <button
      onClick={onToggle}
      className={`px-5 py-2 rounded-lg text-sm font-bold uppercase tracking-wider transition-all ${
        running
          ? 'bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-900/30'
          : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30'
      }`}
    >
      {running ? '■ Stop Agent' : '▶ Start Agent'}
    </button>
  )
}

export default function Dashboard() {
  const data = useTradesData()
  const [agentRunning, setAgentRunning] = useState(data.agent_running)

  useEffect(() => {
    setAgentRunning(data.agent_running)
  }, [data.agent_running])

  const latestEquity = data.equity_curve.length > 0
    ? data.equity_curve[data.equity_curve.length - 1].equity
    : 0
  const startEquity = data.equity_curve.length > 0
    ? data.equity_curve[0].equity
    : 0
  const totalReturn = startEquity > 0 ? ((latestEquity - startEquity) / startEquity * 100) : 0
  const latestCash = data.equity_curve.length > 0
    ? data.equity_curve[data.equity_curve.length - 1].cash
    : 0

  const handleToggle = async () => {
    const next = !agentRunning
    setAgentRunning(next)
    try {
      await fetch('/api/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ running: next }),
      })
    } catch {
      // UI-only toggle if no backend
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-100 tracking-tight">FinRL Trading Dashboard</h1>
            <p className="text-xs text-gray-500 mt-1">
              Last updated: {data.last_updated ? new Date(data.last_updated).toLocaleString() : 'Never'}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <StatusBadge running={agentRunning} />
            <ToggleButton running={agentRunning} onToggle={handleToggle} />
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Portfolio Value" value={formatCurrency(latestEquity)} />
          <StatCard label="Total Return" value={`${totalReturn >= 0 ? '+' : ''}${totalReturn.toFixed(2)}%`} />
          <StatCard label="Cash Available" value={formatCurrency(latestCash)} />
          <StatCard label="Open Positions" value={data.positions.length} sub={`${data.trade_history.length} total trades`} />
        </div>

        {/* Equity Chart */}
        <EquityChart curve={data.equity_curve} />

        {/* Positions & Trade History */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PositionsTable positions={data.positions} />
          <TradeHistory trades={data.trade_history} />
        </div>
      </div>
    </div>
  )
}

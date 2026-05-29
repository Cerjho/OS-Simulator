// dashboard/src/components/GanttChart.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import React, { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer, Cell
} from 'recharts';

// Premium high-fidelity curated HSL/HEX color palette tokens matching standard PIDs
const PALETTE = [
  '#6366f1', // Indigo
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#ec4899', // Pink
  '#06b6d4', // Cyan
  '#8b5cf6', // Violet
  '#3b82f6', // Blue
  '#ef4444', // Red
];

export default function GanttChart({ gantt = [], currentTick = 0, width = '100%', height = 280 }) {
  // Transform canonical backend Gantt intervals into standard floating Recharts horizontal blocks
  const chartData = useMemo(() => {
    if (!gantt || !gantt.length) return [];
    return gantt.map((entry, idx) => ({
      id: `${entry.pid}-${idx}`,
      name: `P${entry.pid}`,
      pid: entry.pid,
      // Pass lower and upper tick bounds as a range array vector to support floating bars
      range: [entry.start_tick, entry.end_tick],
      duration: entry.end_tick - entry.start_tick,
      // FE-BUG-01 fix: Use backend color if available, fall back to PALETTE
      fill: entry.color || PALETTE[entry.pid % PALETTE.length],
    }));
  }, [gantt]);

  // Determine dynamic domain upper bounds to ensure active line renders clearly
  const maxDomain = useMemo(() => {
    let maxEnd = currentTick;
    gantt.forEach(g => { if (g.end_tick > maxEnd) maxEnd = g.end_tick; });
    return Math.max(maxEnd + 5, 20);
  }, [gantt, currentTick]);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-900 text-white p-3 rounded-lg border border-slate-700 shadow-xl text-xs">
          <p className="font-bold text-indigo-400">Process: {data.name}</p>
          <p>Start Tick: <span className="font-semibold">{data.range[0]}</span></p>
          <p>End Tick: <span className="font-semibold">{data.range[1]}</span></p>
          <p>Duration: <span className="font-semibold">{data.duration} units</span></p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-slate-800 shadow-2xl flex flex-col h-full">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-sm font-semibold text-slate-300 tracking-wider uppercase">
          CPU Execution Gantt Trace
        </h3>
        <span className="text-xs bg-indigo-500/10 text-indigo-400 px-2.5 py-0.5 rounded-full font-mono">
          Tick: {currentTick}
        </span>
      </div>
      
      <div style={{ width }} className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={chartData}
            margin={{ top: 10, right: 20, left: 10, bottom: 20 }}
          >
            <XAxis
              type="number"
              domain={[0, maxDomain]}
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
            />
            <YAxis
              type="category"
              dataKey="name"
              stroke="#64748b"
              tick={{ fill: '#cbd5e1', fontSize: 11, fontWeight: 600 }}
              width={40}
            />
            <Tooltip content={<CustomTooltip />} />
            
            {/* Draw active clock reference pointer */}
            <ReferenceLine
              x={currentTick}
              stroke="#ef4444"
              strokeWidth={2}
              strokeDasharray="4 4"
              label={{
                value: 'Active',
                position: 'top',
                fill: '#ef4444',
                fontSize: 10,
                fontWeight: 'bold',
              }}
            />

            <Bar dataKey="range" radius={[4, 4, 4, 4]} barSize={16}>
              {chartData.map((entry) => (
                <Cell key={entry.id} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

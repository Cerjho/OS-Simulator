// dashboard/src/components/MetricsHistory.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import React, { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

// Distinct curated HSL/HEX color mappings associated with canonical metrics strings
const METRIC_COLORS = {
  cpu_utilization: '#10b981',    // Emerald
  page_fault_rate: '#ec4899',    // Pink
  memory_utilization: '#3b82f6', // Blue
  throughput: '#f59e0b',         // Amber
  default: '#8b5cf6',            // Violet
};

// Formats telemetry variable labels into clean legible UI presentation strings
const formatMetricLabel = (keyStr) => {
  return keyStr
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export default function MetricsHistory({
  history = [],
  metricsToShow = ['cpu_utilization', 'page_fault_rate', 'memory_utilization'],
  width = '100%',
  height = 240,
}) {
  const safeHistory = useMemo(() => (Array.isArray(history) ? history : []), [history]);
  const safeMetrics = useMemo(() => (Array.isArray(metricsToShow) ? metricsToShow : []), [metricsToShow]);
  const yAxisMax = useMemo(() => {
    const values = safeHistory.flatMap((row) => (
      safeMetrics
        .map((metricKey) => Number(row?.[metricKey]))
        .filter((value) => Number.isFinite(value))
    ));
    const maxValue = values.length ? Math.max(...values) : 0;
    return maxValue > 1 ? maxValue * 1.1 : 1;
  }, [safeHistory, safeMetrics]);
  const isPercentageScale = yAxisMax <= 1;

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-900 text-white p-3 rounded-lg border border-slate-700 shadow-xl text-xs font-sans">
          <p className="font-bold text-slate-300 pb-1 border-b border-slate-800 mb-1.5">
            Simulation Tick: <span className="font-mono text-indigo-400">{label}</span>
          </p>
          {payload.map((entry) => (
            <div key={entry.dataKey} className="flex justify-between items-center space-x-4 my-0.5">
              <span style={{ color: entry.color }} className="font-semibold">
                {formatMetricLabel(entry.dataKey)}:
              </span>
              <span className="font-mono font-bold text-white">
                {typeof entry.value === 'number' ? entry.value.toFixed(3) : entry.value}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-slate-800 shadow-2xl flex flex-col h-full">
      <div className="flex justify-between items-center mb-1">
        <h3 className="text-sm font-semibold text-slate-300 tracking-wider uppercase">
          Subsystem Telemetry Metrics History
        </h3>
        <span className="text-[10px] text-slate-500 font-mono">
          Samples: {safeHistory.length}
        </span>
      </div>

      <div style={{ width }} className="flex-1 min-h-0 mt-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={safeHistory}
            margin={{ top: 10, right: 10, left: -15, bottom: 5 }}
          >
            <XAxis
              dataKey="tick"
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              label={{ value: 'Simulation Tick', position: 'insideBottomRight', offset: -5, fill: '#64748b', fontSize: 10 }}
            />
            <YAxis
              domain={[0, yAxisMax]}
              stroke="#64748b"
              tick={{ fill: '#cbd5e1', fontSize: 10 }}
              width={40}
              tickFormatter={(v) => (
                isPercentageScale ? `${(v * 100).toFixed(0)}%` : Number(v).toFixed(2)
              )}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 6 }}
              formatter={(value) => <span className="text-slate-300 font-medium">{formatMetricLabel(value)}</span>}
            />

            {safeMetrics.map((metricKey) => (
              <Line
                key={metricKey}
                type="monotone"
                dataKey={metricKey}
                stroke={METRIC_COLORS[metricKey] || METRIC_COLORS.default}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5, stroke: '#ffffff', strokeWidth: 1.5 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

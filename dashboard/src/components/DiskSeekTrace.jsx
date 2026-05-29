// dashboard/src/components/DiskSeekTrace.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import React, { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceDot
} from 'recharts';

export default function DiskSeekTrace({ seekTrace = [], currentHead = 53, totalCylinders = 200, width = '100%', height = 240 }) {
  // Transform standard sequential numerical trace positions into linear chartable nodes
  const { chartData, computedSeekDistance } = useMemo(() => {
    const validTrace = Array.isArray(seekTrace) ? seekTrace : [];
    const data = [];
    let accumSeek = 0;
    let prev = currentHead;

    // Build timeline trace path nodes
    validTrace.forEach((entry, idx) => {
      // Backend sends objects: {from_cylinder, to_cylinder, distance}
      const cyl = Number(entry?.to_cylinder ?? entry?.cylinder ?? entry);

      if (!Number.isFinite(cyl)) return;

      const distance = Number.isFinite(Number(entry?.distance))
        ? Number(entry.distance)
        : Math.abs(cyl - prev);

      accumSeek += distance;
      data.push({
        sequence: idx + 1,
        cylinder: cyl,
        distance,
      });
      prev = cyl;
    });

    // If trace is empty, insert initial active disk arm location anchor
    if (!data.length) {
      data.push({
        sequence: 0,
        cylinder: currentHead,
        distance: 0,
      });
    }

    return { chartData: data, computedSeekDistance: accumSeek };
  }, [seekTrace, currentHead]);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-900 text-white p-2.5 rounded-lg border border-slate-700 shadow-xl text-xs font-sans">
          <p className="font-bold text-cyan-400">Request Seq #{data.sequence}</p>
          <p>Target Cylinder: <span className="font-mono text-white">{data.cylinder}</span></p>
          {data.distance > 0 && <p>Seek Step: <span className="font-mono text-slate-300">{data.distance} tracks</span></p>}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-slate-800 shadow-2xl flex flex-col h-full">
      <div className="flex justify-between items-center mb-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-300 tracking-wider uppercase">
            Disk Arm Head Movement Trace
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Active Head Position: <strong className="text-cyan-400 font-mono">#{currentHead}</strong> • Trace maps serviced I/O cylinder path over time
          </p>
        </div>
        <div className="text-right">
          <span className="text-lg font-bold text-indigo-400 font-mono">
            {computedSeekDistance} <span className="text-xs font-sans font-normal text-slate-400">tracks</span>
          </span>
          <span className="text-[10px] text-slate-500 block uppercase tracking-tight font-sans">
            Total Seek Distance
          </span>
        </div>
      </div>

      <div style={{ width }} className="flex-1 min-h-0 mt-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 15, right: 15, left: 0, bottom: 5 }}
          >
            <XAxis
              dataKey="sequence"
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              label={{ value: 'Request Sequence', position: 'insideBottomRight', offset: -5, fill: '#64748b', fontSize: 10 }}
            />
            <YAxis
              domain={[0, Math.max(totalCylinders - 1, 199)]}
              stroke="#64748b"
              tick={{ fill: '#cbd5e1', fontSize: 10, fontFamily: 'monospace' }}
              width={35}
            />
            <Tooltip content={<CustomTooltip />} />
            
            {/* Draw active glowing pointer overlay highlighting exact currentHead endpoint */}
            {chartData.length > 0 && (
              <ReferenceDot
                x={chartData[chartData.length - 1].sequence}
                y={chartData[chartData.length - 1].cylinder}
                r={6}
                fill="#06b6d4"
                stroke="#ffffff"
                strokeWidth={2}
              />
            )}

            <Line
              type="monotone"
              dataKey="cylinder"
              stroke="#06b6d4"
              strokeWidth={2.5}
              dot={{ stroke: '#0891b2', strokeWidth: 2, r: 4, fill: '#1e293b' }}
              activeDot={{ r: 7, stroke: '#ffffff', strokeWidth: 2, fill: '#06b6d4' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

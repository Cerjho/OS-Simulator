// dashboard/src/components/ProcessTable.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import React, { useState, useMemo } from 'react';

export default function ProcessTable({ processes = [], onSort }) {
  const [internalSortCol, setInternalSortCol] = useState('pid');
  const [internalSortAsc, setInternalSortAsc] = useState(true);

  // Fallback internal sorting mechanism mapping state records gracefully if external prop hook is absent
  const sortedProcesses = useMemo(() => {
    if (!processes || !Array.isArray(processes)) return [];
    const validList = [...processes];
    
    return validList.sort((a, b) => {
      let valA = a[internalSortCol];
      let valB = b[internalSortCol];

      // Standardize null/undefined comparisons
      if (valA === undefined) valA = '';
      if (valB === undefined) valB = '';

      if (typeof valA === 'string') {
        const cmp = valA.localeCompare(valB);
        return internalSortAsc ? cmp : -cmp;
      }

      return internalSortAsc ? valA - valB : valB - valA;
    });
  }, [processes, internalSortCol, internalSortAsc]);

  // Handle header click triggers delegating sorting logic cleanly
  const handleHeaderClick = (columnName) => {
    if (onSort && typeof onSort === 'function') {
      onSort(columnName);
    } else {
      // Manage internal component sorting states natively
      if (internalSortCol === columnName) {
        setInternalSortAsc(!internalSortAsc);
      } else {
        setInternalSortCol(columnName);
        setInternalSortAsc(true);
      }
    }
  };

  // Maps canonical process state string values to tailored UI color badge token layouts
  const renderStateBadge = (stateStr) => {
    const rawState = (stateStr || '').toLowerCase();
    let colorStyles = 'bg-slate-500/10 text-slate-400 border-slate-500/30'; // default terminated/unknown

    if (rawState.includes('running')) {
      colorStyles = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    } else if (rawState.includes('ready')) {
      colorStyles = 'bg-blue-500/10 text-blue-400 border-blue-500/30';
    } else if (rawState.includes('blocked')) {
      colorStyles = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    } else if (rawState.includes('waiting')) {
      colorStyles = 'bg-purple-500/10 text-purple-400 border-purple-500/30';
    } else if (rawState.includes('zombie')) {
      colorStyles = 'bg-red-500/10 text-red-400 border-red-500/30';
    }

    return (
      <span className={`px-2.5 py-1 rounded-md text-xs font-semibold border tracking-wide uppercase inline-block ${colorStyles}`}>
        {stateStr || 'Unknown'}
      </span>
    );
  };

  // Structurally mapped layout headers cataloguing active fields
  const headers = [
    { label: 'PID', key: 'pid', align: 'text-center', width: 'w-16' },
    { label: 'Name', key: 'name', align: 'text-left', width: 'w-28' },
    { label: 'State', key: 'state', align: 'text-center', width: 'w-28' },
    { label: 'Priority', key: 'priority', align: 'text-center', width: 'w-20' },
    { label: 'Remaining', key: 'remaining_burst', align: 'text-center', width: 'w-24' },
    { label: 'Waiting', key: 'waiting_time', align: 'text-center', width: 'w-20' },
    { label: 'Turnaround', key: 'turnaround_time', align: 'text-center', width: 'w-24' },
  ];

  return (
    <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col h-full">
      <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-800 flex justify-between items-center">
        <h3 className="text-sm font-semibold text-slate-300 tracking-wider uppercase">
          Active Thread & Process Queue Management
        </h3>
        <span className="text-xs text-slate-500">
          Total Registered: <strong className="text-slate-400 font-mono">{sortedProcesses.length}</strong>
        </span>
      </div>

      <div className="overflow-x-auto flex-1">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-900/80 text-slate-400 text-[11px] uppercase tracking-wider font-semibold border-b border-slate-800/80 select-none">
              {headers.map((h) => (
                <th
                  key={h.key}
                  onClick={() => handleHeaderClick(h.key)}
                  className={`py-3 px-3 cursor-pointer hover:text-indigo-400 hover:bg-slate-800/30 transition-colors ${h.align} ${h.width}`}
                >
                  <div className={`flex items-center space-x-1 justify-${h.align.includes('center') ? 'center' : 'start'}`}>
                    <span>{h.label}</span>
                    {/* Render visual sort arrow directional cues */}
                    <span className="text-[9px] text-slate-600">
                      {internalSortCol === h.key ? (internalSortAsc ? '▲' : '▼') : '↕'}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-xs divide-y divide-slate-800/40 font-mono text-slate-300">
            {sortedProcesses.length > 0 ? (
              sortedProcesses.map((proc) => (
                <tr
                  key={proc.pid}
                  className="hover:bg-slate-800/20 transition-colors group"
                >
                  <td className="py-2.5 px-3 text-center text-indigo-400 font-bold font-sans">
                    {proc.pid}
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-white font-sans">
                    <div className="flex flex-col">
                      <span>{proc.name}</span>
                      {proc.parent_pid !== undefined && proc.parent_pid !== null && (
                        <span className="text-[9px] text-slate-500 mt-0.5 uppercase tracking-wider">
                          Parent: PID {proc.parent_pid}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-center font-sans">
                    {renderStateBadge(proc.state)}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className="bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                      {proc.priority}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-200">
                    {proc.remaining_burst} <span className="text-[10px] text-slate-500">U</span>
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-400">
                    {proc.waiting_time} <span className="text-[10px] text-slate-600">T</span>
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-400">
                    {proc.turnaround_time} <span className="text-[10px] text-slate-600">T</span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={headers.length} className="py-8 text-center text-slate-600 font-sans italic text-xs">
                  No active processes instantiated in execution context. Use process injection forms to allocate new threads.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

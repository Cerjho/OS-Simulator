// dashboard/src/components/ControlPanel.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import React, { useState, useEffect } from 'react';

const DEFAULT_EXPERIMENT_PRESETS = [
  { name: 'standard_mix', description: 'Standard CPU workload profile mix' },
  { name: 'io_heavy', description: 'I/O intensive process workload' },
  { name: 'memory_pressure', description: 'Aggressive virtual memory frame footprint' },
  { name: 'deadlock_demo', description: 'Induce circular Wait-For RAG dependencies' },
];

export default function ControlPanel({
  isConnected = false,
  isPaused = false,
  activeAlgorithms = {},
  buildApiUrl = (path) => path,
  onStart,
  onStop,
  onPauseResume,
  onStep,
  onInjectProcess,
  onUpdateConfig,
  onRunExperiment,
}) {
  // Localized process injection state footprint
  const [injectForm, setInjectForm] = useState({
    name: 'P1',
    burst: 10,
    priority: 5,
    memory_pages: 4,
  });

  // Localized hardware configuration parameter selections
  const [selectedCpuAlgo, setSelectedCpuAlgo] = useState('round_robin');
  const [selectedMemAlgo, setSelectedMemAlgo] = useState('lru');
  const [selectedDiskAlgo, setSelectedDiskAlgo] = useState('sstf');

  // Discovered experiment preset scripts cache
  const [experimentPresets, setExperimentPresets] = useState([]);

  // Sync active parameters cleanly if modified externally
  useEffect(() => {
    if (activeAlgorithms?.cpu) setSelectedCpuAlgo(activeAlgorithms.cpu);
    if (activeAlgorithms?.memory) setSelectedMemAlgo(activeAlgorithms.memory);
    if (activeAlgorithms?.disk) setSelectedDiskAlgo(activeAlgorithms.disk);
  }, [activeAlgorithms]);

  // Discover and populate profile preset workload scripts via Config API endpoints dynamically
  useEffect(() => {
    let isDisposed = false;
    let retryTimer = null;
    let retryCount = 0;
    const maxRetries = 3;

    const loadPresets = async () => {
      try {
        const res = await fetch(buildApiUrl('/api/experiments'));
        if (!res.ok) {
          throw new Error(`Failed preset discovery with status ${res.status}`);
        }
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
          throw new Error('No experiment presets returned');
        }

        if (!isDisposed) {
          setExperimentPresets(data);
        }
        return true;
      } catch (err) {
        if (!isDisposed) {
          setExperimentPresets((current) => (
            current.length ? current : DEFAULT_EXPERIMENT_PRESETS
          ));
        }
        return false;
      }
    };

    const loadWithRetry = async () => {
      const loaded = await loadPresets();
      retryCount += 1;
      if (!loaded && !isDisposed && retryCount < maxRetries) {
        retryTimer = setTimeout(loadWithRetry, 2000);
      }
    };

    loadWithRetry();

    return () => {
      isDisposed = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [buildApiUrl]);

  // Handle configuration modifications mapping partial PUT request payloads
  const handleConfigChange = (section, key, value) => {
    if (section === 'cpu') setSelectedCpuAlgo(value);
    if (section === 'memory') setSelectedMemAlgo(value);
    if (section === 'disk') setSelectedDiskAlgo(value);

    if (onUpdateConfig) {
      // Map schema layout exactly matching expected API models
      let payload = {};
      if (section === 'cpu') payload = { scheduler: { algorithm: value } };
      if (section === 'memory') payload = { memory: { algorithm: value } };
      if (section === 'disk') payload = { disk: { scheduling: value } };
      onUpdateConfig(payload);
    }
  };

  const handleInjectSubmit = (e) => {
    e.preventDefault();
    if (onInjectProcess) {
      onInjectProcess({
        name: injectForm.name,
        burst: Number(injectForm.burst),
        priority: Number(injectForm.priority),
        memory_pages: Number(injectForm.memory_pages),
      });
      // Increment default naming identifier cleanly for subsequent injection spawns
      const nextNum = Number(injectForm.name.replace(/\D/g, '')) + 1 || Math.floor(Math.random() * 100);
      setInjectForm((prev) => ({ ...prev, name: `P${nextNum}` }));
    }
  };

  return (
    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-slate-800 shadow-2xl flex flex-col h-full min-h-0 overflow-y-auto space-y-4">
      {/* Simulation Master Engine Lifecycle Controllers */}
      <div>
        <div className="flex justify-between items-center mb-2.5">
          <h3 className="text-sm font-semibold text-slate-300 tracking-wider uppercase">
            Master Simulation Lifecycle Controls
          </h3>
          <span className="flex items-center space-x-1.5">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-[10px] font-mono text-slate-400">
              {isConnected ? 'WS Connected' : 'Offline'}
            </span>
          </span>
        </div>

        <div className="grid grid-cols-4 gap-2">
          <button
            onClick={onStart}
            disabled={!isConnected}
            className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-2 px-3 rounded-lg text-xs shadow-lg shadow-emerald-950 transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
          >
            Start Engine
          </button>
          <button
            onClick={onPauseResume}
            disabled={!isConnected}
            className="bg-amber-600 hover:bg-amber-500 text-white font-semibold py-2 px-3 rounded-lg text-xs shadow-lg shadow-amber-950 transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
          >
            {isPaused ? 'Resume' : 'Pause'}
          </button>
          <button
            onClick={onStep}
            disabled={!isConnected}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 px-3 rounded-lg text-xs shadow-lg shadow-indigo-950 transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
          >
            Step Tick
          </button>
          <button
            onClick={onStop}
            disabled={!isConnected}
            className="bg-red-600 hover:bg-red-500 text-white font-semibold py-2 px-3 rounded-lg text-xs shadow-lg shadow-red-950 transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
          >
            Terminate
          </button>
        </div>
      </div>

      {/* Hardware Parameter Dropdown Configuration Tier */}
      <div className="pt-3 border-t border-slate-800">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Subsystem Operational Algorithm Policies
        </h4>
        <div className="space-y-2.5 text-xs">
          <div>
            <label className="block text-[11px] text-slate-500 mb-1">CPU Scheduling Algorithm</label>
            <select
              value={selectedCpuAlgo}
              onChange={(e) => handleConfigChange('cpu', 'algorithm', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-md px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
            >
              <option value="fcfs">FCFS (First-Come First-Served)</option>
              <option value="sjf">SJF (Shortest Job First)</option>
              <option value="srtf">SRTF (Shortest Remaining Time)</option>
              <option value="priority">Priority Tier Scheduling</option>
              <option value="round_robin">Round Robin (RR)</option>
              <option value="mlfq">MLFQ (Multi-Level Feedback)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] text-slate-500 mb-1">Page Replacement Policy</label>
            <select
              value={selectedMemAlgo}
              onChange={(e) => handleConfigChange('memory', 'algorithm', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-md px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
            >
              <option value="fifo">FIFO (First-In First-Out)</option>
              <option value="lru">LRU (Least Recently Used)</option>
              <option value="clock">Clock Second Chance</option>
              <option value="optimal">Optimal Strategy</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] text-slate-500 mb-1">Disk Arm Scheduling Engine</label>
            <select
              value={selectedDiskAlgo}
              onChange={(e) => handleConfigChange('disk', 'scheduling', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-md px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
            >
              <option value="fcfs">FCFS Seek</option>
              <option value="sstf">SSTF (Shortest Seek Time)</option>
              <option value="scan">SCAN Elevator Track</option>
              <option value="c-scan">C-SCAN Circular Elevator</option>
              <option value="look">LOOK Engine</option>
              <option value="c-look">C-LOOK Sweep</option>
            </select>
          </div>
        </div>
      </div>

      {/* Dynamic Subsystem Process Injection Form Block */}
      <div className="pt-3 border-t border-slate-800">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Runtime Process Workload Injection
        </h4>
        <form onSubmit={handleInjectSubmit} className="space-y-2 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] text-slate-500 mb-0.5">Name Identifier</label>
              <input
                type="text"
                required
                value={injectForm.name}
                onChange={(e) => setInjectForm({ ...injectForm, name: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono focus:outline-none focus:border-indigo-500 text-xs"
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-500 mb-0.5">CPU Burst Units</label>
              <input
                type="number"
                min="1"
                required
                value={injectForm.burst}
                onChange={(e) => setInjectForm({ ...injectForm, burst: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono focus:outline-none focus:border-indigo-500 text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] text-slate-500 mb-0.5">Tier Priority (0-20)</label>
              <input
                type="number"
                min="0"
                max="20"
                required
                value={injectForm.priority}
                onChange={(e) => setInjectForm({ ...injectForm, priority: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono focus:outline-none focus:border-indigo-500 text-xs"
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-500 mb-0.5">Memory Pages</label>
              <input
                type="number"
                min="1"
                required
                value={injectForm.memory_pages}
                onChange={(e) => setInjectForm({ ...injectForm, memory_pages: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono focus:outline-none focus:border-indigo-500 text-xs"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full mt-1 bg-slate-800 hover:bg-slate-700 text-indigo-400 border border-indigo-500/30 font-semibold py-1.5 px-3 rounded text-xs transition-colors active:scale-95"
          >
            Inject Spawned Process
          </button>
        </form>
      </div>

      {/* Preset Evaluation Workload Scripts Selectors */}
      <div className="pt-3 border-t border-slate-800 flex-1 flex flex-col">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Evaluation Preset Workloads
        </h4>
        <div className="grid grid-cols-2 gap-2 flex-1 auto-rows-max overflow-y-auto pr-1">
          {experimentPresets.map((preset) => (
            <button
              key={preset.name}
              onClick={() => onRunExperiment && onRunExperiment(preset.name)}
              className="text-left bg-slate-950 hover:bg-slate-800/80 p-2 rounded-lg border border-slate-800/80 transition-all active:scale-95 flex flex-col justify-between"
              title={preset.description}
            >
              <span className="font-mono text-xs font-bold text-slate-200 block truncate">
                {preset.name}
              </span>
              <span className="text-[10px] text-slate-500 block line-clamp-2 leading-tight mt-1">
                {preset.description}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

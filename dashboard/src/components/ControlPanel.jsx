// dashboard/src/components/ControlPanel.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
// Refactored: Algorithm config dropdowns moved to ConfigPanel. This component
// now focuses on runtime operations: lifecycle, process injection, and experiments.
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
  buildApiUrl = (path) => path,
  onStart,
  onStop,
  onPauseResume,
  onStep,
  onInjectProcess,
  onRunExperiment,
}) {
  // Localized process injection state footprint
  const [injectForm, setInjectForm] = useState({
    name: 'P1',
    burst: 10,
    priority: 5,
    memory_pages: 4,
  });

  // Discovered experiment preset scripts cache
  const [experimentPresets, setExperimentPresets] = useState([]);

  // Experiment detail preview state
  const [previewData, setPreviewData] = useState(null);
  const [previewName, setPreviewName] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

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

  // Fetch experiment detail for preview
  const handlePreviewToggle = async (presetName) => {
    if (previewName === presetName) {
      // Toggle off
      setPreviewName(null);
      setPreviewData(null);
      return;
    }

    setPreviewName(presetName);
    setLoadingPreview(true);
    setPreviewData(null);

    try {
      const res = await fetch(buildApiUrl(`/api/experiments/${presetName}`));
      if (res.ok) {
        const data = await res.json();
        setPreviewData(data);
      }
    } catch (err) {
      console.error('[ControlPanel] Preview fetch error:', err);
    } finally {
      setLoadingPreview(false);
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
            Simulation Controls
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

      {/* Dynamic Subsystem Process Injection Form Block */}
      <div className="pt-3 border-t border-slate-800">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Runtime Process Injection
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
      <div className="pt-3 border-t border-slate-800 flex-1 flex flex-col min-h-0">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
          Evaluation Preset Workloads
        </h4>
        <div className="grid grid-cols-2 gap-2 auto-rows-max overflow-y-auto pr-1">
          {experimentPresets.map((preset) => (
            <div key={preset.name} className="flex flex-col">
              <button
                onClick={() => handlePreviewToggle(preset.name)}
                className={`text-left p-2 rounded-lg border transition-all active:scale-95 flex flex-col justify-between ${
                  previewName === preset.name
                    ? 'bg-indigo-950/40 border-indigo-500/40'
                    : 'bg-slate-950 hover:bg-slate-800/80 border-slate-800/80'
                }`}
                title={preset.description}
              >
                <span className="font-mono text-xs font-bold text-slate-200 block truncate">
                  {preset.name}
                </span>
                <span className="text-[10px] text-slate-500 block line-clamp-2 leading-tight mt-1">
                  {preset.description}
                </span>
              </button>
            </div>
          ))}
        </div>

        {/* Experiment Preview Popover */}
        {previewName && (
          <div className="mt-2 p-2.5 bg-slate-950/80 border border-slate-700/60 rounded-lg animate-fadeIn">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] text-indigo-400 font-bold uppercase tracking-wider">
                {previewName} — Preview
              </span>
              <button
                onClick={() => { setPreviewName(null); setPreviewData(null); }}
                className="text-[10px] text-slate-500 hover:text-slate-300"
              >
                ✕
              </button>
            </div>

            {loadingPreview && (
              <span className="text-[10px] text-slate-500 animate-pulse">Loading…</span>
            )}

            {previewData && (
              <div className="space-y-1.5 text-[10px]">
                <div className="text-slate-400">
                  <span className="text-slate-500 font-semibold">Workload: </span>
                  {previewData.workload_name}
                </div>

                {/* Config overrides */}
                {(previewData.scheduler || previewData.deadlock || previewData.processes_config) && (
                  <div className="space-y-0.5">
                    <span className="text-slate-500 font-semibold block">Config Overrides:</span>
                    {previewData.scheduler && (
                      <div className="text-slate-400 pl-2 font-mono">
                        scheduler: {JSON.stringify(previewData.scheduler)}
                      </div>
                    )}
                    {previewData.deadlock && (
                      <div className="text-slate-400 pl-2 font-mono">
                        deadlock: {JSON.stringify(previewData.deadlock)}
                      </div>
                    )}
                    {previewData.processes_config && (
                      <div className="text-slate-400 pl-2 font-mono">
                        processes: {JSON.stringify(previewData.processes_config)}
                      </div>
                    )}
                  </div>
                )}

                {/* Process list */}
                {previewData.processes && previewData.processes.length > 0 && (
                  <div>
                    <span className="text-slate-500 font-semibold block mb-0.5">
                      Processes ({previewData.processes.length}):
                    </span>
                    <div className="max-h-24 overflow-y-auto space-y-0.5">
                      {previewData.processes.map((p, i) => (
                        <div key={i} className="flex gap-2 text-slate-400 font-mono pl-2">
                          <span className="text-indigo-400 font-bold">{p.name}</span>
                          <span>b={p.burst}</span>
                          <span>p={p.priority}</span>
                          <span>m={p.memory_pages}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  onClick={() => {
                    onRunExperiment && onRunExperiment(previewName);
                    setPreviewName(null);
                    setPreviewData(null);
                  }}
                  className="w-full mt-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-1.5 px-3 rounded text-[10px] transition-all active:scale-95 shadow-lg shadow-indigo-950"
                >
                  ▶ Run {previewName}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

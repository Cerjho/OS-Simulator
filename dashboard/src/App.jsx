// dashboard/src/App.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useWebSocket } from './hooks/useWebSocket';

// Internal subsystem interface components
import ControlPanel from './components/ControlPanel';
import ProcessTable from './components/ProcessTable';
import GanttChart from './components/GanttChart';
import MemoryMap from './components/MemoryMap';
import MetricsHistory from './components/MetricsHistory';
import RAGGraph from './components/RAGGraph';
import DiskSeekTrace from './components/DiskSeekTrace';

export default function App() {
  const apiBaseUrl = useMemo(() => {
    const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim();
    if (!configuredBase) return '';
    return configuredBase.endsWith('/') ? configuredBase.slice(0, -1) : configuredBase;
  }, []);

  const buildApiUrl = useCallback(
    (path) => `${apiBaseUrl}${path}`,
    [apiBaseUrl]
  );

  const websocketUrl = useMemo(() => {
    const configuredWsUrl = import.meta.env.VITE_WS_URL?.trim();
    if (configuredWsUrl) return configuredWsUrl;

    if (apiBaseUrl) {
      try {
        const parsedApiBase = new URL(apiBaseUrl);
        const wsProtocol = parsedApiBase.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${wsProtocol}//${parsedApiBase.host}/ws/realtime`;
      } catch (err) {
        console.warn('[Dashboard] Invalid VITE_API_BASE_URL; falling back to current host.');
      }
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${window.location.host}/ws/realtime`;
  }, [apiBaseUrl]);

  // Establish decoupled continuous bidirectional socket connection interfacing directly with shared backend Kernel
  const { state, isConnected, sendCommand, reconnect } = useWebSocket(websocketUrl);

  // Maintain Section 17.2 metrics telemetry histories arrays cleanly
  const [metricsHistory, setMetricsHistory] = useState([]);

  // Extract canonical simulation state variables safely
  const currentTick = state?.tick || 0;
  const isPaused = state?.clock?.paused || false;
  const processes = state?.processes || [];
  const gantt = state?.gantt || [];
  const memoryState = state?.memory || {};
  const diskState = state?.disk || {};
  const deadlockState = state?.deadlock || {};

  // Extract underlying configuration algorithm tokens safely
  const activeAlgorithms = useMemo(() => {
    // Attempt extracting from configuration snapshot payload attributes if available
    return {
      cpu: state?.config?.scheduler?.algorithm || 'round_robin',
      memory: state?.config?.memory?.algorithm || 'lru',
      disk: state?.config?.disk?.scheduling || 'sstf',
    };
  }, [state]);

  // Aggregate detected cycle process array slices to resolve deadlocked entity status flags
  const deadlockedPids = useMemo(() => {
    if (!deadlockState?.cycles || !Array.isArray(deadlockState.cycles)) return [];
    const pidsSet = new Set();
    deadlockState.cycles.forEach((cycleArr) => {
      if (Array.isArray(cycleArr)) {
        cycleArr.forEach((p) => pidsSet.add(p));
      }
    });
    return Array.from(pidsSet);
  }, [deadlockState]);

  // Build metrics history locally from WebSocket state instead of polling REST
  useEffect(() => {
    if (!state || state.tick === undefined) return;

    const record = {
      tick: state.tick,
      cpu_utilization: state.cpu?.utilization ?? 0,
      page_fault_rate: state.memory?.page_fault_rate ?? 0,
      memory_utilization: state.memory?.utilization ?? 0,
    };

    setMetricsHistory((prev) => {
      const next = [...prev, record];
      // Cap to last 100 entries for performance
      return next.length > 100 ? next.slice(-100) : next;
    });
  }, [state?.tick]);

  // Control API REST Endpoint Invocation wrappers delegating state triggers seamlessly
  const handleStart = useCallback(() => {
    fetch(buildApiUrl('/api/control/start'), { method: 'POST' }).catch((err) =>
      console.error('[Control API] Start error:', err)
    );
  }, [buildApiUrl]);

  const handleStop = useCallback(() => {
    fetch(buildApiUrl('/api/control/stop'), { method: 'POST' }).catch((err) =>
      console.error('[Control API] Stop error:', err)
    );
  }, [buildApiUrl]);

  const handlePauseResume = useCallback(() => {
    const targetEndpoint = isPaused ? 'resume' : 'pause';
    // Delegate through explicit API endpoints natively or fallback to WebSocket command channels
    fetch(buildApiUrl(`/api/control/${targetEndpoint}`), { method: 'POST' })
      .catch((err) => {
        sendCommand(targetEndpoint);
      });
  }, [buildApiUrl, isPaused, sendCommand]);

  const handleStep = useCallback(() => {
    fetch(buildApiUrl('/api/control/step'), { method: 'POST' }).catch((err) =>
      console.error('[Control API] Step error:', err)
    );
  }, [buildApiUrl]);

  const handleInjectProcess = useCallback((processSpec) => {
    fetch(buildApiUrl('/api/processes/inject'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(processSpec),
    }).catch((err) => console.error('[Control API] Process Injection error:', err));
  }, [buildApiUrl]);

  const handleUpdateConfig = useCallback((partialConfigPayload) => {
    fetch(buildApiUrl('/api/config'), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(partialConfigPayload),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Config update failed with status ${res.status}`);
        reconnect();
      })
      .catch((err) => console.error('[Config API] Partial update error:', err));
  }, [buildApiUrl, reconnect]);

  const handleRunExperiment = useCallback((presetNameStr) => {
    fetch(buildApiUrl('/api/experiments/run'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: presetNameStr }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Experiment run failed with status ${res.status}`);
        reconnect();
      })
      .catch((err) => console.error('[Config API] Experiment runner execution error:', err));
  }, [buildApiUrl, reconnect]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased p-4 selection:bg-indigo-500 selection:text-white">
      {/* Premium Dashboard Global Visual Header */}
      <header className="mb-5 pb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-900/40 p-4 rounded-xl border border-slate-800/50 backdrop-blur">
        <div>
          <div className="flex items-center space-x-3">
            <span className="bg-gradient-to-tr from-indigo-500 to-violet-500 text-white font-black px-3 py-1 rounded-lg text-sm tracking-wider shadow-md">
              OS101
            </span>
            <h1 className="text-xl font-bold bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              Advanced Master Kernel Telemetry Dashboard
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1 pl-1">
            Real-time interactive monitoring console supporting dynamic preemption, virtual memory paging maps, disk arm seeks, and RAG cycle trackers.
          </p>
        </div>

        {/* Global Operational Metrics Overlay Counter */}
        <div className="flex items-center space-x-6 bg-slate-950/80 px-4 py-2.5 rounded-lg border border-slate-800 shadow-inner">
          <div className="text-center">
            <span className="text-[10px] text-slate-500 block uppercase tracking-wider font-semibold">
              Global Clock
            </span>
            <span className="text-lg font-bold text-indigo-400 font-mono">
              {currentTick} <span className="text-xs text-slate-600 font-sans font-normal">ticks</span>
            </span>
          </div>
          <div className="h-8 w-px bg-slate-800"></div>
          <div className="text-center">
            <span className="text-[10px] text-slate-500 block uppercase tracking-wider font-semibold">
              Engine Status
            </span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded uppercase tracking-wide inline-block mt-0.5 ${
              isConnected
                ? isPaused
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-red-500/10 text-red-400 border border-red-500/20'
            }`}>
              {isConnected ? (isPaused ? 'Paused' : 'Active') : 'Offline'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Structural Interface Grid Container Layout */}
      <main className="flex flex-col space-y-4">
        {/* Upper Two-Column Dashboard Layout Section */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left Column: Direct Hardware Control Panel & Active Thread Table */}
          <div className="lg:col-span-4 flex flex-col space-y-4 h-[920px]">
            <div className="h-2/5 min-h-[360px]">
              <ControlPanel
                isConnected={isConnected}
                isPaused={isPaused}
                activeAlgorithms={activeAlgorithms}
                buildApiUrl={buildApiUrl}
                onStart={handleStart}
                onStop={handleStop}
                onPauseResume={handlePauseResume}
                onStep={handleStep}
                onInjectProcess={handleInjectProcess}
                onUpdateConfig={handleUpdateConfig}
                onRunExperiment={handleRunExperiment}
              />
            </div>
            <div className="h-3/5 flex-1 overflow-hidden">
              <ProcessTable processes={processes} />
            </div>
          </div>

          {/* Right Column: Execution Gantt Traces, Memory Allocation Maps, & Time-Series History */}
          <div className="lg:col-span-8 flex flex-col space-y-4 h-[920px]">
            <div className="h-1/3">
              <GanttChart gantt={gantt} currentTick={currentTick} height="100%" />
            </div>
            <div className="h-1/3">
              <MemoryMap
                blocks={memoryState?.allocated_blocks || memoryState?.blocks || []}
                totalFrames={memoryState?.total_frames || 64}
              />
            </div>
            <div className="h-1/3">
              <MetricsHistory
                history={metricsHistory}
                metricsToShow={['cpu_utilization', 'page_fault_rate', 'memory_utilization']}
                height="100%"
              />
            </div>
          </div>
        </div>

        {/* Bottom Row Full-Width Grid Section: Visual RAG Graph & Disk Head Seek Vectors */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 h-[360px]">
          {/* Left Half: Multi-dimensional Force Graph rendering dynamic deadlock state loops */}
          <div className="h-full overflow-hidden">
            <RAGGraph
              allocations={deadlockState?.allocations || {}}
              requests={deadlockState?.requests || {}}
              deadlocked_pids={deadlockedPids}
            />
          </div>

          {/* Right Half: IO Disk Arm trace path chart tracking seek cost distance accumulators */}
          <div className="h-full overflow-hidden">
            <DiskSeekTrace
              seekTrace={diskState?.trace || diskState?.seek_trace || []}
              currentHead={diskState?.current_head ?? 53}
              totalCylinders={diskState?.total_cylinders ?? 200}
              height="100%"
            />
          </div>
        </div>
      </main>

      {/* Exquisite minimalist footer signing state parameters */}
      <footer className="mt-6 pt-4 border-t border-slate-900 text-center text-xs text-slate-600 font-mono">
        OS101 Multi-Agent Core Engine Suite • Production Telemetry Frontend Console v2.0
      </footer>
    </div>
  );
}

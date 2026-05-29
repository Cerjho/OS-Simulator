// dashboard/src/components/ConfigPanel.jsx
// Full simulation configuration editor with collapsible accordion sections.
import React, { useState, useEffect, useCallback } from 'react';

// ── Reusable Accordion Section ──────────────────────────────────────────────
function AccordionSection({ title, icon, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-slate-800/60 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 bg-slate-900/40 hover:bg-slate-800/50 transition-colors text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wide">
          <span className="text-sm">{icon}</span>
          {title}
        </span>
        <span className={`text-slate-500 text-[10px] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>
      {isOpen && (
        <div className="px-3 py-2.5 space-y-2 bg-slate-950/30 animate-fadeIn">
          {children}
        </div>
      )}
    </div>
  );
}

// ── Reusable Input Components ───────────────────────────────────────────────
function NumberField({ label, value, onChange, min, max, step = 1, hint }) {
  return (
    <div>
      <label className="block text-[10px] text-slate-500 mb-0.5">{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono focus:outline-none focus:border-indigo-500 text-xs"
      />
      {hint && <span className="text-[9px] text-slate-600 mt-0.5 block">{hint}</span>}
    </div>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <div>
      <label className="block text-[10px] text-slate-500 mb-0.5">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono focus:outline-none focus:border-indigo-500 text-xs"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function ToggleField({ label, value, onChange }) {
  return (
    <div className="flex items-center justify-between py-0.5">
      <label className="text-[10px] text-slate-500">{label}</label>
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 ${value ? 'bg-indigo-600' : 'bg-slate-700'
          }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform duration-200 shadow ${value ? 'translate-x-4' : 'translate-x-0.5'
            }`}
        />
      </button>
    </div>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <div>
      <label className="block text-[10px] text-slate-500 mb-0.5">{label}</label>
      <div className="w-full bg-slate-950/50 border border-slate-800/50 rounded px-2 py-1 text-slate-400 font-mono text-xs cursor-not-allowed">
        {String(value)}
      </div>
    </div>
  );
}

// ── Default config shape (mirrors core/config.py dataclass defaults) ────────
const DEFAULT_CONFIG = {
  clock: { tick_rate_ms: 100, max_ticks: 10000, auto_start: false },
  cpu: { cores: 1, context_switch_cost: 2 },
  scheduler: { algorithm: 'round_robin', time_quantum: 4, preemptive: true, aging_interval: 50 },
  memory: { algorithm: 'lru', total_frames: 64, page_size_kb: 4, swap_enabled: true, tlb_size: 16 },
  filesystem: { type: 'fat', total_blocks: 512, block_size_kb: 4 },
  disk: { scheduling: 'sstf', cylinders: 200, initial_head: 53, seek_time_per_track: 1 },
  processes: { initial_load: 5, auto_spawn: true, spawn_interval_ticks: 20 },
  deadlock: { detection_interval: 10, recovery_strategy: 'terminate_youngest' },
  logging: { level: 'INFO', log_to_file: true, log_path: 'logs/simulation.log' },
};

// Prototype pollution guard — reject dangerous keys in bracket notation
const DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

// Allowlist of valid config sections (mirrors DEFAULT_CONFIG keys)
const VALID_SECTIONS = new Set(Object.keys(DEFAULT_CONFIG));

// Deep merge helper (safe: skips prototype-polluting keys)
function deepMerge(target, source) {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    if (DANGEROUS_KEYS.has(key)) continue;
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      result[key] = deepMerge(result[key] || {}, source[key]);
    } else if (source[key] !== undefined && source[key] !== null) {
      result[key] = source[key];
    }
  }
  return result;
}

// ── Main Component ──────────────────────────────────────────────────────────
export default function ConfigPanel({ buildApiUrl, onUpdateConfig, isConnected }) {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [isDirty, setIsDirty] = useState(false);
  const [applying, setApplying] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  // Fetch current config on mount
  useEffect(() => {
    let cancelled = false;
    fetch(buildApiUrl('/api/config'))
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled && data) {
          setConfig(deepMerge(DEFAULT_CONFIG, data));
        }
      })
      .catch(() => { });
    return () => { cancelled = true; };
  }, [buildApiUrl]);

  // Update a nested config value (safe: validates section/key against allowlist)
  const updateField = useCallback((section, key, value) => {
    if (!VALID_SECTIONS.has(section) || DANGEROUS_KEYS.has(key)) return;
    setConfig((prev) => {
      const sectionObj = prev[section];
      if (!sectionObj || !Object.prototype.hasOwnProperty.call(sectionObj, key)) return prev;
      return { ...prev, [section]: { ...sectionObj, [key]: value } };
    });
    setIsDirty(true);
    setStatusMsg(null);
  }, []);

  // Apply all changes as a single batch
  const handleApply = useCallback(() => {
    if (!onUpdateConfig) return;
    setApplying(true);
    setStatusMsg(null);

    fetch(buildApiUrl('/api/config'), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
      .then((res) => {
        if (!res.ok) return res.json().then((d) => { throw new Error(d?.detail?.errors?.join(', ') || `Status ${res.status}`); });
        return res.json();
      })
      .then(() => {
        setIsDirty(false);
        setStatusMsg({ type: 'success', text: 'Configuration applied — kernel restarted' });
        setTimeout(() => setStatusMsg(null), 4000);
        onUpdateConfig();
      })
      .catch((err) => {
        setStatusMsg({ type: 'error', text: `Failed: ${err.message}` });
      })
      .finally(() => setApplying(false));
  }, [config, buildApiUrl, onUpdateConfig]);

  // Reset to server state
  const handleReset = useCallback(() => {
    fetch(buildApiUrl('/api/config'))
      .then((res) => res.json())
      .then((data) => {
        if (data) setConfig(deepMerge(DEFAULT_CONFIG, data));
        setIsDirty(false);
        setStatusMsg(null);
      })
      .catch(() => { });
  }, [buildApiUrl]);

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Scrollable config sections */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1 pb-2">

        {/* ── A: Clock & Timing ── */}
        <AccordionSection title="Clock & Timing" icon="⏱" defaultOpen={false}>
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="Tick Rate (ms)"
              value={config.clock.tick_rate_ms}
              onChange={(v) => updateField('clock', 'tick_rate_ms', v)}
              min={10} max={1000} step={10}
              hint="Simulation speed"
            />
            <NumberField
              label="Max Ticks"
              value={config.clock.max_ticks}
              onChange={(v) => updateField('clock', 'max_ticks', v)}
              min={100} max={100000}
            />
          </div>
          <ToggleField
            label="Auto-start on launch"
            value={config.clock.auto_start}
            onChange={(v) => updateField('clock', 'auto_start', v)}
          />
        </AccordionSection>

        {/* ── B: CPU ── */}
        <AccordionSection title="CPU" icon="🔲" defaultOpen={false}>
          <div className="grid grid-cols-2 gap-2">
            <ReadOnlyField label="Cores" value={config.cpu.cores} />
            <NumberField
              label="Context Switch Cost (ticks)"
              value={config.cpu.context_switch_cost}
              onChange={(v) => updateField('cpu', 'context_switch_cost', v)}
              min={0} max={10}
            />
          </div>
        </AccordionSection>

        {/* ── C: Scheduler ── */}
        <AccordionSection title="Process Scheduler" icon="📋" defaultOpen={true}>
          <SelectField
            label="Algorithm"
            value={config.scheduler.algorithm}
            onChange={(v) => updateField('scheduler', 'algorithm', v)}
            options={[
              { value: 'fcfs', label: 'FCFS (First-Come First-Served)' },
              { value: 'sjf', label: 'SJF (Shortest Job First)' },
              { value: 'srtf', label: 'SRTF (Shortest Remaining Time)' },
              { value: 'priority', label: 'Priority Scheduling' },
              { value: 'round_robin', label: 'Round Robin (RR)' },
              { value: 'mlfq', label: 'MLFQ (Multi-Level Feedback)' },
            ]}
          />
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="Time Quantum"
              value={config.scheduler.time_quantum}
              onChange={(v) => updateField('scheduler', 'time_quantum', v)}
              min={1} max={100}
              hint={config.scheduler.algorithm === 'round_robin' || config.scheduler.algorithm === 'mlfq' ? 'Active for RR/MLFQ' : 'Not used by this algorithm'}
            />
            <NumberField
              label="Aging Interval"
              value={config.scheduler.aging_interval}
              onChange={(v) => updateField('scheduler', 'aging_interval', v)}
              min={1} max={200}
            />
          </div>
          <ToggleField
            label="Preemptive scheduling"
            value={config.scheduler.preemptive}
            onChange={(v) => updateField('scheduler', 'preemptive', v)}
          />
        </AccordionSection>

        {/* ── D: Memory ── */}
        <AccordionSection title="Virtual Memory" icon="🧠" defaultOpen={true}>
          <SelectField
            label="Page Replacement Algorithm"
            value={config.memory.algorithm}
            onChange={(v) => updateField('memory', 'algorithm', v)}
            options={[
              { value: 'fifo', label: 'FIFO (First-In First-Out)' },
              { value: 'lru', label: 'LRU (Least Recently Used)' },
              { value: 'clock', label: 'Clock (Second Chance)' },
              { value: 'optimal', label: 'Optimal (Theoretical)' },
            ]}
          />
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="Total Frames"
              value={config.memory.total_frames}
              onChange={(v) => updateField('memory', 'total_frames', v)}
              min={8} max={1024}
            />
            <NumberField
              label="Page Size (KB)"
              value={config.memory.page_size_kb}
              onChange={(v) => updateField('memory', 'page_size_kb', v)}
              min={1} max={64}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="TLB Size (entries)"
              value={config.memory.tlb_size}
              onChange={(v) => updateField('memory', 'tlb_size', v)}
              min={4} max={256}
            />
            <div className="flex items-end pb-0.5">
              <ToggleField
                label="Swap Enabled"
                value={config.memory.swap_enabled}
                onChange={(v) => updateField('memory', 'swap_enabled', v)}
              />
            </div>
          </div>
        </AccordionSection>

        {/* ── E: Filesystem ── */}
        <AccordionSection title="Filesystem" icon="📁" defaultOpen={false}>
          <SelectField
            label="Filesystem Type"
            value={config.filesystem.type}
            onChange={(v) => updateField('filesystem', 'type', v)}
            options={[
              { value: 'fat', label: 'FAT (File Allocation Table)' },
              { value: 'inode', label: 'inode (Unix-style Indexed)' },
            ]}
          />
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="Total Blocks"
              value={config.filesystem.total_blocks}
              onChange={(v) => updateField('filesystem', 'total_blocks', v)}
              min={64} max={4096}
            />
            <NumberField
              label="Block Size (KB)"
              value={config.filesystem.block_size_kb}
              onChange={(v) => updateField('filesystem', 'block_size_kb', v)}
              min={1} max={64}
            />
          </div>
        </AccordionSection>

        {/* ── F: Disk I/O ── */}
        <AccordionSection title="Disk I/O" icon="💿" defaultOpen={true}>
          <SelectField
            label="Disk Scheduling Algorithm"
            value={config.disk.scheduling}
            onChange={(v) => updateField('disk', 'scheduling', v)}
            options={[
              { value: 'fcfs', label: 'FCFS Seek' },
              { value: 'sstf', label: 'SSTF (Shortest Seek Time)' },
              { value: 'scan', label: 'SCAN (Elevator)' },
              { value: 'c-scan', label: 'C-SCAN (Circular Elevator)' },
              { value: 'look', label: 'LOOK' },
              { value: 'c-look', label: 'C-LOOK' },
            ]}
          />
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="Cylinders"
              value={config.disk.cylinders}
              onChange={(v) => updateField('disk', 'cylinders', v)}
              min={10} max={10000}
            />
            <NumberField
              label="Initial Head Position"
              value={config.disk.initial_head}
              onChange={(v) => updateField('disk', 'initial_head', v)}
              min={0} max={config.disk.cylinders - 1}
            />
          </div>
          <NumberField
            label="Seek Time per Track"
            value={config.disk.seek_time_per_track}
            onChange={(v) => updateField('disk', 'seek_time_per_track', v)}
            min={1} max={10}
          />
        </AccordionSection>

        {/* ── G: Process Generation ── */}
        <AccordionSection title="Process Generation" icon="⚙️" defaultOpen={false}>
          <NumberField
            label="Initial Process Load"
            value={config.processes.initial_load}
            onChange={(v) => updateField('processes', 'initial_load', v)}
            min={0} max={50}
            hint="Processes created at tick 0"
          />
          <ToggleField
            label="Auto-spawn new processes"
            value={config.processes.auto_spawn}
            onChange={(v) => updateField('processes', 'auto_spawn', v)}
          />
          {config.processes.auto_spawn && (
            <NumberField
              label="Spawn Interval (ticks)"
              value={config.processes.spawn_interval_ticks}
              onChange={(v) => updateField('processes', 'spawn_interval_ticks', v)}
              min={5} max={200}
            />
          )}
        </AccordionSection>

        {/* ── H: Deadlock ── */}
        <AccordionSection title="Deadlock Detection" icon="🔒" defaultOpen={false}>
          <NumberField
            label="Detection Interval (ticks)"
            value={config.deadlock.detection_interval}
            onChange={(v) => updateField('deadlock', 'detection_interval', v)}
            min={1} max={100}
          />
          <SelectField
            label="Recovery Strategy"
            value={config.deadlock.recovery_strategy}
            onChange={(v) => updateField('deadlock', 'recovery_strategy', v)}
            options={[
              { value: 'terminate_youngest', label: 'Terminate Youngest Process' },
              { value: 'terminate_lowest', label: 'Terminate Lowest Priority' },
              { value: 'resource_preempt', label: 'Resource Preemption' },
              { value: 'none', label: 'None (Detect Only)' },
            ]}
          />
        </AccordionSection>

        {/* ── I: Logging ── */}
        <AccordionSection title="Logging" icon="📝" defaultOpen={false}>
          <SelectField
            label="Log Level"
            value={config.logging.level}
            onChange={(v) => updateField('logging', 'level', v)}
            options={[
              { value: 'DEBUG', label: 'DEBUG — Verbose' },
              { value: 'INFO', label: 'INFO — Standard' },
              { value: 'WARNING', label: 'WARNING — Quiet' },
              { value: 'ERROR', label: 'ERROR — Minimal' },
            ]}
          />
          <ToggleField
            label="Log to file"
            value={config.logging.log_to_file}
            onChange={(v) => updateField('logging', 'log_to_file', v)}
          />
          {config.logging.log_to_file && (
            <ReadOnlyField label="Log Path" value={config.logging.log_path} />
          )}
        </AccordionSection>
      </div>

      {/* ── Sticky Apply Bar ── */}
      <div className="pt-2 border-t border-slate-800 space-y-2 flex-shrink-0">
        {statusMsg && (
          <div className={`text-[10px] px-2 py-1 rounded ${statusMsg.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'bg-red-500/10 text-red-400 border border-red-500/20'
            }`}>
            {statusMsg.text}
          </div>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleApply}
            disabled={!isDirty || applying || !isConnected}
            className={`flex-1 font-semibold py-1.5 px-3 rounded-lg text-xs transition-all active:scale-95 shadow-lg ${isDirty
                ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-950'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
              } disabled:opacity-50 disabled:pointer-events-none`}
          >
            {applying ? 'Applying…' : isDirty ? '⚡ Apply Configuration' : 'No Changes'}
          </button>
          <button
            type="button"
            onClick={handleReset}
            disabled={!isDirty}
            className="bg-slate-800 hover:bg-slate-700 text-slate-400 font-semibold py-1.5 px-3 rounded-lg text-xs transition-colors active:scale-95 disabled:opacity-30 disabled:pointer-events-none"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}

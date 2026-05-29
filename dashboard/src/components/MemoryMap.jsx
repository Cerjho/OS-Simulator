// dashboard/src/components/MemoryMap.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import React, { useMemo, useState } from 'react';

// Consistent beautiful HSL/HEX color mappings matching main application design tokens
const PALETTE = [
  'bg-indigo-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-pink-500',
  'bg-cyan-500',
  'bg-violet-500',
  'bg-blue-500',
  'bg-red-500',
];

export default function MemoryMap({ blocks = [], totalFrames = 64 }) {
  const [hoveredBlock, setHoveredBlock] = useState(null);

  // Compute total allocation percentages cleanly
  const { segments, percentUsed } = useMemo(() => {
    const validBlocks = Array.isArray(blocks) ? blocks : [];
    let allocatedFrames = 0;
    
    // Sort blocks sequentially by base address to ensure continuous linear visual segments
    const sorted = [...validBlocks].sort((a, b) => a.base - b.base);
    const computedSegments = [];
    let cursor = 0;

    sorted.forEach((block, idx) => {
      // Inject gray background tracking slice if unallocated gap exists before current block
      if (block.base > cursor) {
        const gapSize = block.base - cursor;
        computedSegments.push({
          id: `free-${cursor}`,
          type: 'free',
          base: cursor,
          size: gapSize,
          widthPercent: (gapSize / totalFrames) * 100,
        });
      }

      // Add actual allocated process footprint region
      allocatedFrames += block.size;
      computedSegments.push({
        id: `alloc-${block.base}-${block.pid}`,
        type: 'allocated',
        base: block.base,
        size: block.size,
        pid: block.pid,
        widthPercent: (block.size / totalFrames) * 100,
        colorClass: PALETTE[block.pid % PALETTE.length],
      });

      cursor = block.base + block.size;
    });

    // Fill remaining terminal memory footprint space with unallocated gaps
    if (cursor < totalFrames) {
      const remainingGap = totalFrames - cursor;
      computedSegments.push({
        id: `free-${cursor}`,
        type: 'free',
        base: cursor,
        size: remainingGap,
        widthPercent: (remainingGap / totalFrames) * 100,
      });
    }

    const calculatedPct = totalFrames > 0 ? ((allocatedFrames / totalFrames) * 100).toFixed(1) : 0;
    return { segments: computedSegments, percentUsed: calculatedPct };
  }, [blocks, totalFrames]);

  return (
    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-slate-800 shadow-2xl flex flex-col h-full">
      <div className="flex justify-between items-center mb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-300 tracking-wider uppercase">
            Physical Memory Frames Map
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Total Framework Space: <span className="text-slate-400 font-mono">{totalFrames} frames</span>
          </p>
        </div>
        <div className="text-right">
          <span className="text-lg font-bold text-emerald-400 font-mono">
            {percentUsed}%
          </span>
          <span className="text-xs text-slate-400 block uppercase tracking-tight">Utilized</span>
        </div>
      </div>

      {/* Render segmented dynamic allocation bar container */}
      <div className="relative h-8 w-full bg-slate-800/80 rounded-lg overflow-hidden flex border border-slate-700/50 shadow-inner">
        {segments.map((seg) => (
          <div
            key={seg.id}
            style={{ width: `${Math.max(seg.widthPercent, 0.5)}%` }}
            className={`h-full transition-all duration-300 cursor-pointer border-r border-slate-900/40 relative group ${
              seg.type === 'allocated' ? seg.colorClass : 'bg-slate-700/30 hover:bg-slate-700/50'
            }`}
            onMouseEnter={() => setHoveredBlock(seg)}
            onMouseLeave={() => setHoveredBlock(null)}
          >
            {/* Direct CSS Tooltip fallback support */}
            <div className="absolute inset-0" title={seg.type === 'allocated' ? `PID: ${seg.pid} | Base: ${seg.base} | Size: ${seg.size}` : `Free | Base: ${seg.base} | Size: ${seg.size}`} />
          </div>
        ))}
      </div>

      {/* Interactive granular telemetry display overlay footer */}
      <div className="mt-3 h-6 flex items-center justify-between text-xs px-1">
        {hoveredBlock ? (
          <div className="flex items-center space-x-3 text-slate-300 animate-fadeIn">
            <span className="font-semibold text-indigo-400">
              {hoveredBlock.type === 'allocated' ? `Process P${hoveredBlock.pid}` : 'Unallocated Space'}
            </span>
            <span className="text-slate-500">|</span>
            <span>Base Address: <strong className="font-mono text-white">{hoveredBlock.base}</strong></span>
            <span className="text-slate-500">|</span>
            <span>Segment Size: <strong className="font-mono text-white">{hoveredBlock.size} frames</strong></span>
          </div>
        ) : (
          <span className="text-slate-500 italic text-[11px]">
            Hover over interactive visual memory segments to view specific process boundary allocations.
          </span>
        )}

        <div className="flex items-center space-x-2">
          <span className="w-2.5 h-2.5 rounded-full bg-slate-700/50 inline-block border border-slate-600"></span>
          <span className="text-[11px] text-slate-400">Free Segment</span>
        </div>
      </div>
    </div>
  );
}

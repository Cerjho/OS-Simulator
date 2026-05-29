// dashboard/src/components/RAGGraph.jsx
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import React, { useMemo, useRef, useState, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function RAGGraph({ allocations = {}, requests = {}, deadlocked_pids = [] }) {
  // Measure container dimensions for responsive ForceGraph rendering
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 500, height: 280 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        if (w > 0 && h > 0) {
          setDimensions({ width: Math.floor(w), height: Math.floor(h) });
        }
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  // Construct dynamic graph node sets and directional wait-for links cleanly
  const graphData = useMemo(() => {
    const nodesMap = new Map();
    const links = [];

    const safeAllocations = allocations || {};
    const safeRequests = requests || {};
    const safeDeadlocked = Array.isArray(deadlocked_pids) ? deadlocked_pids : [];

    // Collect process nodes and their associated assigned resource edges
    Object.entries(safeAllocations).forEach(([pidStr, resList]) => {
      const numericPid = Number(pidStr);
      const pNodeId = `P${numericPid}`;

      if (!nodesMap.has(pNodeId)) {
        nodesMap.set(pNodeId, {
          id: pNodeId,
          name: `P${numericPid}`,
          type: 'process',
          pid: numericPid,
          isDeadlocked: safeDeadlocked.includes(numericPid),
        });
      }

      if (Array.isArray(resList)) {
        resList.forEach((resId) => {
          const rNodeId = `R-${resId}`;
          if (!nodesMap.has(rNodeId)) {
            nodesMap.set(rNodeId, {
              id: rNodeId,
              name: resId,
              type: 'resource',
            });
          }
          // Allocation edges point from the Resource node directly to the Process node holder
          links.push({
            source: rNodeId,
            target: pNodeId,
            type: 'allocation',
            color: '#10b981', // Emerald for active allocation
          });
        });
      }
    });

    // Collect outstanding pending requests mapping processes waiting on targets
    Object.entries(safeRequests).forEach(([pidStr, reqResId]) => {
      // Skip PIDs with no active request — prevents orphan process nodes
      if (!reqResId) return;
      
      const numericPid = Number(pidStr);
      const pNodeId = `P${numericPid}`;
      const rNodeId = `R-${reqResId}`;

      if (!nodesMap.has(pNodeId)) {
        nodesMap.set(pNodeId, {
          id: pNodeId,
          name: `P${numericPid}`,
          type: 'process',
          pid: numericPid,
          isDeadlocked: safeDeadlocked.includes(numericPid),
        });
      }

      if (!nodesMap.has(rNodeId)) {
        nodesMap.set(rNodeId, {
          id: rNodeId,
          name: reqResId,
          type: 'resource',
        });
      }

      // Request edges point from the waiting Process node directly to the requested Resource node
      links.push({
        source: pNodeId,
        target: rNodeId,
        type: 'request',
        color: '#f59e0b', // Amber for blocked requests
      });
    });

    return {
      nodes: Array.from(nodesMap.values()),
      links,
    };
  }, [allocations, requests, deadlocked_pids]);

  // Customized canvas object rendering explicit visual mappings matching specification rules
  const renderCustomNode = (node, ctx, globalScale) => {
    const label = node.name;
    const baseRadius = 8;
    const resSize = 14;

    // Draw primary structural element shape
    if (node.type === 'process') {
      ctx.beginPath();
      ctx.arc(node.x, node.y, baseRadius, 0, 2 * Math.PI, false);
      // Deadlocked process nodes rendered in highly prominent alert red
      ctx.fillStyle = node.isDeadlocked ? '#ef4444' : '#3b82f6';
      ctx.fill();
      ctx.strokeStyle = node.isDeadlocked ? '#fca5a5' : '#bfdbfe';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    } else {
      // Resource block square layout
      ctx.fillStyle = '#8b5cf6'; // Premium vibrant violet
      ctx.fillRect(node.x - resSize / 2, node.y - resSize / 2, resSize, resSize);
      ctx.strokeStyle = '#ddd6fe';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(node.x - resSize / 2, node.y - resSize / 2, resSize, resSize);
    }

    // Render legible descriptive string labels
    const fontSize = Math.max(10, 12 / Math.max(globalScale, 0.5));
    ctx.font = `600 ${fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = node.isDeadlocked ? '#fca5a5' : '#cbd5e1';
    ctx.fillText(label, node.x, node.y + (node.type === 'process' ? baseRadius + 4 : resSize / 2 + 4));
  };

  return (
    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-slate-800 shadow-2xl flex flex-col h-full">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-sm font-semibold text-slate-300 tracking-wider uppercase">
          Resource Allocation Graph (RAG)
        </h3>
        {deadlocked_pids && deadlocked_pids.length > 0 ? (
          <span className="text-xs bg-red-500/10 text-red-400 px-2 py-0.5 rounded-full border border-red-500/20 font-bold animate-pulse">
            Deadlock Detected
          </span>
        ) : (
          <span className="text-xs text-slate-500 font-mono">Status: Safe</span>
        )}
      </div>

      <div ref={containerRef} className="flex-1 relative rounded-lg overflow-hidden border border-slate-800/80 bg-slate-950/40">
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}
            nodeCanvasObject={renderCustomNode}
            nodeLabel="name"
            linkDirectionalArrowLength={5}
            linkDirectionalArrowRelPos={1}
            linkColor="color"
            linkWidth={1.5}
            d3VelocityDecay={0.3}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-600 italic font-sans p-4 text-center">
            Graph unpopulated. Instantiate threads holding/requesting specific resource handles to visualize allocation chains.
          </div>
        )}
      </div>

      <div className="mt-2.5 flex items-center justify-between text-[10px] text-slate-400 px-1 font-sans">
        <div className="flex items-center space-x-3">
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block border border-blue-300"></span>
            <span>Process</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 bg-violet-500 inline-block border border-violet-300"></span>
            <span>Resource</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block border border-red-300 animate-ping"></span>
            <span>Deadlocked</span>
          </span>
        </div>
        <div className="flex items-center space-x-2 text-slate-500">
          <span>➔ Allocation</span>
          <span>➔ Request</span>
        </div>
      </div>
    </div>
  );
}

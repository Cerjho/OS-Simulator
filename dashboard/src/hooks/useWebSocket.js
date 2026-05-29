// dashboard/src/hooks/useWebSocket.js
// Phase: 8 — Visualization & Dashboard
// Owner: Dashboard Agent
import { useState, useEffect, useRef, useCallback } from 'react';

export function useWebSocket(url) {
  const [state, setState] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const shouldReconnectRef = useRef(true);
  const maxRetries = 10;

  const connect = useCallback(() => {
    if (!shouldReconnectRef.current) return;
    if (wsRef.current && (
      wsRef.current.readyState === WebSocket.CONNECTING
      || wsRef.current.readyState === WebSocket.OPEN
    )) {
      return;
    }

    if (retryCountRef.current >= maxRetries) {
      console.warn(`[WebSocket] Maximum reconnection attempts (${maxRetries}) reached.`);
      return;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        retryCountRef.current = 0; // Reset reconnection retry accumulator
      };

      ws.onmessage = (event) => {
        try {
          const parsedData = JSON.parse(event.data);
          // Only apply top-level canonical kernel snapshot slices to operational state
          if (parsedData && parsedData.tick !== undefined && !parsedData.ack) {
            setState(parsedData);
          }
        } catch (err) {
          console.error('[WebSocket] JSON parsing error:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;

        if (!shouldReconnectRef.current) return;

        // Trigger automated exponential or fixed interval backoff connection attempts
        retryCountRef.current += 1;
        if (retryCountRef.current < maxRetries) {
          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, 2000);
        }
      };

      ws.onerror = (err) => {
        // Errors naturally lead to onclose events which handle reconnection logic
      };
    } catch (err) {
      console.error('[WebSocket] Initialization error:', err);
    }
  }, [url]);

  useEffect(() => {
    shouldReconnectRef.current = true;

    // Delay initial connection to avoid React StrictMode mount/unmount churn during development.
    const initialConnectTimer = setTimeout(() => {
      connect();
    }, 0);

    return () => {
      shouldReconnectRef.current = false;
      clearTimeout(initialConnectTimer);
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      // Cleanly unbind connection references upon hook unmounting lifecycle
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const sendCommand = useCallback((cmd) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: cmd }));
    } else {
      console.warn('[WebSocket] Cannot transmit command: socket state is disconnected.');
    }
  }, []);

  const reconnect = useCallback(() => {
    retryCountRef.current = 0;
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setTimeout(() => {
      if (shouldReconnectRef.current) connect();
    }, 50);
  }, [connect]);

  return { state, isConnected, sendCommand, reconnect };
}

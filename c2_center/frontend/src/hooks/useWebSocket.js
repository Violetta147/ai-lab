import { useState, useEffect, useRef, useCallback } from 'react';

const hostname = window.location.hostname;
const API_BASE = `http://${hostname}:8000`;
const WS_BASE = `ws://${hostname}:8000`;

/**
 * Hook for WebSocket connection with auto-reconnect.
 */
export function useWebSocket(path, { onMessage, enabled = true } = {}) {
  const wsRef = useRef(null);
  const [status, setStatus] = useState('disconnected');

  useEffect(() => {
    if (!enabled || !path) return;

    let ws;
    let reconnectTimer;
    let shouldReconnect = true;

    function connect() {
      setStatus('connecting');
      ws = new WebSocket(`${WS_BASE}${path}`);

      ws.onopen = () => {
        setStatus('connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage?.(data);
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };

      ws.onclose = () => {
        setStatus('disconnected');
        if (shouldReconnect) {
          reconnectTimer = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    }

    connect();

    return () => {
      shouldReconnect = false;
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [path, enabled]);

  return { status, ws: wsRef };
}

/**
 * Fetch helper for the C2 Backend API.
 */
export async function apiFetch(endpoint, options = {}) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export { API_BASE, WS_BASE };

import { useEffect, useRef, useCallback } from "react";
import { getOptionChainSocketUrl } from "../lib/api";
import { useDashboardStore } from "../store/useDashboardStore";
import type { OptionChainDelta, OptionChainSnapshot } from "../types";

export function useOptionChainSocket() {
  const setSnapshot = useDashboardStore((state) => state.setSnapshot);
  const applyDelta = useDashboardStore((state) => state.applyDelta);
  const setConnectionStatus = useDashboardStore(
    (state) => state.setConnectionStatus,
  );

  const socketRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const attemptsRef = useRef(0);
  const mountedRef = useRef(true);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "snapshot") {
          setSnapshot(payload as OptionChainSnapshot);
        } else if (payload.type === "delta") {
          applyDelta(payload as OptionChainDelta);
        }
        // Ignore other types (pong, waiting, etc.)
      } catch (error) {
        console.error("WebSocket message parse error:", error);
      }
    },
    [setSnapshot, applyDelta],
  );

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    // Clear any existing connection
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    setConnectionStatus("connecting");
    const url = getOptionChainSocketUrl();
    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => {
      if (!mountedRef.current) return;
      console.log("🟢 WebSocket opened");
      attemptsRef.current = 0;
      setConnectionStatus("connected");

      // Setup ping interval
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = window.setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send("ping");
        }
      }, 20000);
    };

    socket.onmessage = handleMessage;

    socket.onerror = (event) => {
      console.error("WebSocket error:", event);
      // Do NOT close here – let onclose handle cleanup
    };

    socket.onclose = (event) => {
      if (!mountedRef.current) return;
      if (event.code === 1006 && import.meta.env.DEV) {
        console.debug("Strict Mode cleanup – ignoring");
        return;
      }
      console.warn(
        `WebSocket closed: code=${event.code} reason=${event.reason}`,
      );
      setConnectionStatus("disconnected");
      socketRef.current = null;

      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }

      // Reconnect with exponential backoff
      if (mountedRef.current) {
        const delay = Math.min(1000 * Math.pow(2, attemptsRef.current), 8000);
        attemptsRef.current++;
        if (reconnectTimeoutRef.current)
          clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = window.setTimeout(connect, delay);
      }
    };
  }, [handleMessage, setConnectionStatus]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimeoutRef.current)
        clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [connect]);

  return null;
}

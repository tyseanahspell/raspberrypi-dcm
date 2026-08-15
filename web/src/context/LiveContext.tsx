import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getToken } from "../lib/api";
import { useAuth } from "./AuthContext";

type LiveContextValue = {
  revision: number;
  connected: boolean;
};

const LiveContext = createContext<LiveContextValue>({ revision: 0, connected: false });

export function LiveProvider({ children }: { children: ReactNode }) {
  const { username } = useAuth();
  const [revision, setRevision] = useState(0);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!username) return;
    const token = getToken();
    if (!token) return;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/api/v1/ws?token=${token}`);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as { type: string };
      if (message.type !== "ping" && message.type !== "ready") {
        setRevision((value) => value + 1);
      }
    };
    return () => socket.close();
  }, [username]);

  const value = useMemo(() => ({ revision, connected }), [revision, connected]);
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive(): LiveContextValue {
  return useContext(LiveContext);
}

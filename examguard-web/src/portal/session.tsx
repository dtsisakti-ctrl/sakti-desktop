import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, local, session } from "../api/client";
import type { Candidate } from "./types";

const PENDING_INVITE = "eg.portal.invite";

interface PortalSession {
  me: Candidate | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
  /** An invitation link opened before signing in; accepted after login (PRD §28.3). */
  pendingInvite: string | null;
  setPendingInvite: (token: string | null) => void;
}

const Ctx = createContext<PortalSession | null>(null);

export function PortalSessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Candidate | null>(null);
  const [ready, setReady] = useState(false);
  const [pendingInvite, setInvite] = useState<string | null>(local.read(PENDING_INVITE));

  const load = useCallback(async () => {
    if (!session.token) {
      setMe(null);
      setReady(true);
      return;
    }
    try {
      setMe(await api.get<Candidate>("/api/v1/candidate/me"));
    } catch {
      session.setToken(null);
      setMe(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    session.onUnauthorized(() => {
      session.setToken(null);
      setMe(null);
    });
    void load();
  }, [load]);

  const value = useMemo<PortalSession>(() => ({
    me, ready, pendingInvite,
    async login(email, password) {
      const r = await api.post<{ token: string }>("/api/v1/candidate/auth/login", { email, password });
      session.setToken(r.token);
      await load();
    },
    async logout() {
      try {
        await api.post("/api/v1/candidate/auth/logout");
      } catch {
        /* already gone */
      }
      session.setToken(null);
      setMe(null);
    },
    reload: load,
    setPendingInvite(token) {
      local.write(PENDING_INVITE, token);
      setInvite(token);
    },
  }), [me, ready, pendingInvite, load]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePortal(): PortalSession {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePortal outside PortalSessionProvider");
  return v;
}

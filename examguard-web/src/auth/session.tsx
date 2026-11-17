import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, session } from "../api/client";
import type { Me, Membership } from "../api/types";

interface SessionValue {
  me: Me | null;
  ready: boolean;
  org: Membership | null;
  roles: Set<string>;
  isExamAdmin: boolean;
  isOrgAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  switchOrg: (orgId: string) => void;
}

const Ctx = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const [orgId, setOrgId] = useState<string | null>(session.orgId);

  const loadMe = useCallback(async () => {
    if (!session.token) {
      setMe(null);
      setReady(true);
      return;
    }
    try {
      const m = await api.get<Me>("/api/v1/staff/me");
      setMe(m);
      const keep = m.memberships.find((x) => x.org_id === session.orgId) ?? m.memberships[0] ?? null;
      session.setOrg(keep?.org_id ?? null);
      setOrgId(keep?.org_id ?? null);
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
    void loadMe();
  }, [loadMe]);

  const value = useMemo<SessionValue>(() => {
    const org = me?.memberships.find((m) => m.org_id === orgId) ?? null;
    const roles = new Set(org?.roles ?? []);
    return {
      me, ready, org, roles,
      isExamAdmin: roles.has("EXAM_ADMIN"),
      isOrgAdmin: roles.has("ORG_ADMIN"),
      async login(email, password) {
        const r = await api.post<{ token: string }>("/api/v1/staff/auth/login", { email, password });
        session.setToken(r.token);
        await loadMe();
      },
      async logout() {
        try {
          await api.post("/api/v1/staff/auth/logout");
        } catch {
          /* already gone */
        }
        session.setToken(null);
        setMe(null);
      },
      switchOrg(id) {
        session.setOrg(id);
        setOrgId(id);
      },
    };
  }, [me, ready, orgId, loadMe]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession outside SessionProvider");
  return v;
}

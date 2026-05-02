"use client";

import { useEffect, useState } from "react";
import { AUTH_EVENT, AuthUser, getUser, isAuthed } from "@/lib/auth";

interface AuthState {
  user: AuthUser | null;
  authed: boolean;
  /** True until the first client-side render finishes — prevents SSR/CSR mismatch. */
  hydrated: boolean;
}

/**
 * Subscribes to localStorage-backed auth state.
 *
 * - Re-renders on the in-tab `tm:auth-change` event (fired by login/logout/clearSession).
 * - Re-renders on the cross-tab `storage` event so logging out in one tab logs you
 *   out everywhere.
 * - Returns `hydrated=false` on the very first render so consumers can avoid
 *   flashing the wrong UI while the client catches up to localStorage state.
 */
export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({
    user: null,
    authed: false,
    hydrated: false,
  });

  useEffect(() => {
    const sync = () => {
      setState({ user: getUser(), authed: isAuthed(), hydrated: true });
    };
    sync();

    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return state;
}

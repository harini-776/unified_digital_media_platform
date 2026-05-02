"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

/**
 * Redirects to /login?next=<current-path> if the user isn't authenticated.
 *
 * Returns the current auth state so the calling page can render a loading
 * placeholder until `hydrated` is true. (Without that gate, the page would
 * flash unauthenticated content for one frame before the redirect fires.)
 *
 * Note: we intentionally read `window.location` instead of useSearchParams()
 * here. useSearchParams forces every consumer page to wrap itself in a
 * Suspense boundary at static-prerender time, which is unnecessary friction
 * for a hook that only ever runs in an effect (i.e. client-side).
 */
export function useRequireAuth() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.hydrated) return;
    if (auth.authed) return;

    const next = encodeURIComponent(window.location.pathname + window.location.search);
    router.replace(`/login?next=${next}`);
  }, [auth.hydrated, auth.authed, router]);

  return auth;
}

"use client";

import { Loader2 } from "lucide-react";
import { useRequireAuth } from "@/hooks/useRequireAuth";

/**
 * Client-side route guard. Renders children only if the user is authenticated;
 * otherwise the hook fires a redirect to /login?next=<current-path> and we
 * show a brief loading spinner during the transition.
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const auth = useRequireAuth();

  if (!auth.hydrated || !auth.authed) {
    return (
      <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return <>{children}</>;
}

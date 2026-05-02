"use client";

import { Badge } from "@/components/ui/badge";
import { ShieldCheck, ShieldAlert, ShieldX } from "lucide-react";
import type { Verdict } from "@/types";

const verdictConfig: Record<Verdict, { label: string; variant: "success" | "warning" | "danger"; icon: typeof ShieldCheck }> = {
  authentic: { label: "Verified Authentic", variant: "success", icon: ShieldCheck },
  suspicious: { label: "Suspicious", variant: "warning", icon: ShieldAlert },
  manipulated: { label: "Manipulated", variant: "danger", icon: ShieldX },
};

interface VerdictBadgeProps {
  verdict: Verdict;
  size?: "sm" | "lg";
}

export function VerdictBadge({ verdict, size = "sm" }: VerdictBadgeProps) {
  const config = verdictConfig[verdict];
  const Icon = config.icon;

  if (size === "lg") {
    return (
      <div className="flex items-center gap-3">
        <div
          className={`p-3 rounded-full ${
            verdict === "authentic"
              ? "bg-emerald-100 dark:bg-emerald-900/30"
              : verdict === "suspicious"
              ? "bg-amber-100 dark:bg-amber-900/30"
              : "bg-red-100 dark:bg-red-900/30"
          }`}
        >
          <Icon
            className={`w-8 h-8 ${
              verdict === "authentic"
                ? "text-emerald-600 dark:text-emerald-400"
                : verdict === "suspicious"
                ? "text-amber-600 dark:text-amber-400"
                : "text-red-600 dark:text-red-400"
            }`}
          />
        </div>
        <div>
          <p className="text-lg font-semibold">{config.label}</p>
          <p className="text-sm text-muted-foreground">Final Verdict</p>
        </div>
      </div>
    );
  }

  return (
    <Badge variant={config.variant} className="gap-1.5 py-1 px-3">
      <Icon className="w-3.5 h-3.5" />
      {config.label}
    </Badge>
  );
}

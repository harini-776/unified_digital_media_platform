"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface SignalCardProps {
  title: string;
  score: number | null;
  icon: React.ReactNode;
  description: string;
  details?: Record<string, unknown>;
}

export function SignalCard({ title, score, icon, description, details }: SignalCardProps) {
  const displayScore = score ?? 50;
  const getScoreColor = (s: number) => {
    if (s < 30) return "text-emerald-600 dark:text-emerald-400";
    if (s < 60) return "text-amber-600 dark:text-amber-400";
    return "text-red-600 dark:text-red-400";
  };

  const getBarColor = (s: number) => {
    if (s < 30) return "[&>div]:bg-emerald-500";
    if (s < 60) return "[&>div]:bg-amber-500";
    return "[&>div]:bg-red-500";
  };

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {icon}
            <CardTitle className="text-base">{title}</CardTitle>
          </div>
          <span className={cn("text-2xl font-bold tabular-nums", getScoreColor(displayScore))}>
            {score !== null ? `${displayScore.toFixed(0)}%` : "N/A"}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <Progress value={displayScore} className={cn("h-2 mb-3", getBarColor(displayScore))} />
        <p className="text-sm text-muted-foreground">{description}</p>
        {details && Object.keys(details).length > 0 && (
          <div className="mt-3 space-y-1">
            {Object.entries(details).map(([key, val]) => (
              <div key={key} className="flex justify-between text-xs">
                <span className="text-muted-foreground">{key.replace(/_/g, " ")}</span>
                <span className="font-mono">{String(val)}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

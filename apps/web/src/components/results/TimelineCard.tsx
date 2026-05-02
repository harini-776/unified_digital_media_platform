"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Upload, Cpu, CheckCircle2, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface TimelineStep {
  label: string;
  time: string | null;
  icon: React.ReactNode;
  active: boolean;
}

interface TimelineCardProps {
  uploadedAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export function TimelineCard({ uploadedAt, startedAt, completedAt }: TimelineCardProps) {
  const formatTime = (iso: string | null) => {
    if (!iso) return null;
    return new Date(iso).toLocaleString();
  };

  const steps: TimelineStep[] = [
    { label: "Uploaded", time: formatTime(uploadedAt), icon: <Upload className="w-4 h-4" />, active: true },
    { label: "Processing", time: formatTime(startedAt), icon: <Cpu className="w-4 h-4" />, active: !!startedAt },
    { label: "Completed", time: formatTime(completedAt), icon: <CheckCircle2 className="w-4 h-4" />, active: !!completedAt },
  ];

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-primary" />
          <CardTitle className="text-base">Analysis Timeline</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {steps.map((step, i) => (
            <div key={step.label} className="flex items-start gap-3">
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "flex items-center justify-center w-8 h-8 rounded-full border-2",
                    step.active
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-muted text-muted-foreground"
                  )}
                >
                  {step.icon}
                </div>
                {i < steps.length - 1 && (
                  <div className={cn("w-0.5 h-6 mt-1", step.active ? "bg-primary" : "bg-muted")} />
                )}
              </div>
              <div className="pt-1">
                <p className={cn("text-sm font-medium", !step.active && "text-muted-foreground")}>
                  {step.label}
                </p>
                {step.time && <p className="text-xs text-muted-foreground">{step.time}</p>}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getJobStatus, getVideoResult, getVideoStreamUrl } from "@/lib/api";
import { TrustScoreGauge } from "@/components/results/TrustScoreGauge";
import { VerdictBadge } from "@/components/results/VerdictBadge";
import { BlockchainCard } from "@/components/results/BlockchainCard";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Scan, Mic, Ear, Eye, Activity, Share2,
  AlertTriangle, CheckCircle, Brain, ArrowLeft, Info,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import type { Verdict } from "@/types";

// ─── helpers ────────────────────────────────────────────────────────────────

function riskLabel(score: number): string {
  if (score >= 70) return "High risk";
  if (score >= 40) return "Medium risk";
  return "Low risk";
}

function riskCls(score: number | null) {
  if (score === null) return { bar: "bg-muted", text: "text-muted-foreground", badge: "bg-muted text-muted-foreground" };
  if (score >= 70) return { bar: "bg-rose-500",   text: "text-rose-500",   badge: "bg-rose-500/10 text-rose-500 border border-rose-500/20" };
  if (score >= 40) return { bar: "bg-amber-400",  text: "text-amber-500",  badge: "bg-amber-400/10 text-amber-500 border border-amber-400/20" };
  return              { bar: "bg-emerald-500", text: "text-emerald-500", badge: "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20" };
}

// ─── Progress screen ─────────────────────────────────────────────────────────

const STAGES: Record<string, { label: string; pct: number }> = {
  pending:          { label: "Queued — waiting for worker…", pct: 3  },
  processing:       { label: "Starting analysis…",           pct: 8  },
  extracting:       { label: "Extracting frames & audio…",   pct: 18 },
  analyzing:        { label: "Running AI analysis…",         pct: 60 },
  blockchain_check: { label: "Checking blockchain record…",  pct: 90 },
  completed:        { label: "Analysis complete!",           pct: 100 },
};

const STEPS = [
  { key: "pending",          label: "Queued"      },
  { key: "extracting",       label: "Extraction"  },
  { key: "analyzing",        label: "AI Analysis" },
  { key: "blockchain_check", label: "Blockchain"  },
  { key: "completed",        label: "Done"        },
];

function AnalysisProgress({ status, progress }: { status: string; progress: number }) {
  const stage = STAGES[status] ?? { label: status.replace(/_/g, " "), pct: progress };
  const currentIdx = STEPS.findIndex((s) => s.key === status);

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-md space-y-10 text-center">

        {/* Spinner */}
        <div className="flex justify-center">
          <div className="relative w-20 h-20">
            <div className="absolute inset-0 rounded-full border-4 border-primary/15 border-t-primary animate-spin" />
            <Brain className="absolute inset-0 m-auto w-8 h-8 text-primary" />
          </div>
        </div>

        <div className="space-y-1">
          <h2 className="text-xl font-bold">Analysing Video</h2>
          <p className="text-sm text-muted-foreground">{stage.label}</p>
        </div>

        {/* Progress bar */}
        <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-700"
            style={{ width: `${progress || stage.pct}%` }}
          />
        </div>

        {/* Step dots */}
        <div className="flex justify-between">
          {STEPS.map((s, i) => {
            const done = i < currentIdx;
            const active = i === currentIdx;
            return (
              <div key={s.key} className="flex flex-col items-center gap-1.5">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs border-2 transition-colors ${
                  done   ? "bg-primary border-primary text-primary-foreground" :
                  active ? "border-primary text-primary bg-primary/10" :
                           "border-muted text-muted-foreground"
                }`}>
                  {done ? <CheckCircle className="w-3.5 h-3.5" /> : <span>{i + 1}</span>}
                </div>
                <span className={`text-[10px] hidden sm:block ${active ? "text-primary font-medium" : "text-muted-foreground"}`}>
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Signal card ─────────────────────────────────────────────────────────────

interface SignalCardProps {
  icon: React.ReactNode;
  iconBg: string;
  title: string;
  score: number | null;
  description: string;
  details: Record<string, unknown>;
  weight?: number | null;
}

function SignalCard({ icon, iconBg, title, score, description, details, weight }: SignalCardProps) {
  const pct = score ?? 50;
  const cls = riskCls(score);
  const notable = Object.entries(details).filter(([k]) => !["method", "embedding", "note"].includes(k));

  return (
    <div className="rounded-2xl border bg-card p-5 space-y-4 hover:shadow-sm transition-shadow">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${iconBg}`}>
            {icon}
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight">{title}</p>
            {weight != null && (
              <p className="text-xs text-muted-foreground">{Math.round(weight * 100)}% weight</p>
            )}
          </div>
        </div>
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${cls.badge}`}>
          {score !== null ? riskLabel(pct) : "N/A"}
        </span>
      </div>

      {/* Score bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between items-center">
          <span className="text-xs text-muted-foreground">Manipulation score</span>
          <span className={`text-sm font-bold tabular-nums ${cls.text}`}>{pct.toFixed(0)}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${cls.bar}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>

      {/* Details grid */}
      {notable.length > 0 && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1 border-t border-border">
          {notable.map(([k, v]) => (
            <div key={k} className="flex justify-between text-xs pt-1">
              <span className="text-muted-foreground capitalize">{k.replace(/_/g, " ")}</span>
              <span className="font-mono font-medium tabular-nums">{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main results ─────────────────────────────────────────────────────────────

function ResultsContent() {
  const searchParams = useSearchParams();
  const jobId   = searchParams.get("job_id");
  const videoId = searchParams.get("video_id");

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJobStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "completed" || s === "failed" ? false : 1500;
    },
  });

  const jobCompleted = !jobId || jobQuery.data?.status === "completed";

  const resultQuery = useQuery({
    queryKey: ["result", videoId],
    queryFn: () => getVideoResult(videoId!),
    enabled: !!videoId && jobCompleted,
    retry: 3,
  });

  if (!videoId) {
    return (
      <div className="container max-w-lg py-24 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-muted-foreground mx-auto" />
        <p className="text-muted-foreground">No video specified. Upload a video first.</p>
        <Link href="/upload" className="text-primary text-sm hover:underline">Go to upload →</Link>
      </div>
    );
  }

  // Job still running
  if (jobId && jobQuery.data && jobQuery.data.status !== "completed") {
    if (jobQuery.data.status === "failed") {
      return (
        <div className="container max-w-md py-24 text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-destructive/10 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-7 h-7 text-destructive" />
          </div>
          <h2 className="text-xl font-bold">Analysis Failed</h2>
          <p className="text-sm text-destructive bg-destructive/10 rounded-xl px-4 py-3">
            {jobQuery.data.error_message ?? "Unknown error"}
          </p>
          <Link href="/upload" className="text-primary text-sm hover:underline">Try again →</Link>
        </div>
      );
    }
    return <AnalysisProgress status={jobQuery.data.status} progress={jobQuery.data.progress} />;
  }

  // Loading skeleton
  if (!resultQuery.data) {
    return (
      <div className="container max-w-5xl mx-auto py-10 px-4 space-y-6">
        <Skeleton className="h-7 w-52" />
        <div className="grid md:grid-cols-3 gap-6">
          <Skeleton className="h-72 rounded-2xl" />
          <div className="md:col-span-2 space-y-4">
            <Skeleton className="h-36 rounded-2xl" />
            <Skeleton className="h-28 rounded-2xl" />
          </div>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-44 rounded-2xl" />)}
        </div>
      </div>
    );
  }

  const result = resultQuery.data;
  const weights = result.modality_weights ?? {};
  const sig     = result.signals;

  const signals: Omit<SignalCardProps, "score" | "details">[] = [
    {
      icon:        <Scan className="w-4 h-4 text-blue-500" />,
      iconBg:      "bg-blue-500/10",
      title:       "Face Analysis",
      description: "Detects face-swap artifacts, boundary inconsistencies, and lighting anomalies.",
      weight:      weights.face,
    },
    {
      icon:        <Mic className="w-4 h-4 text-purple-500" />,
      iconBg:      "bg-purple-500/10",
      title:       "Voice Analysis",
      description: "Identifies synthetic speech, voice cloning, and TTS artifacts via MFCC analysis.",
      weight:      weights.voice,
    },
    {
      icon:        <Ear className="w-4 h-4 text-orange-500" />,
      iconBg:      "bg-orange-500/10",
      title:       "Lip Sync",
      description: "Measures audio-visual synchronisation to detect dubbing and audio replacement.",
      weight:      weights.lipsync,
    },
    {
      icon:        <Eye className="w-4 h-4 text-teal-500" />,
      iconBg:      "bg-teal-500/10",
      title:       "Blink Detection",
      description: "Analyses blink rate and timing patterns — deepfakes often blink unnaturally.",
      weight:      weights.blink,
    },
    {
      icon:        <Activity className="w-4 h-4 text-pink-500" />,
      iconBg:      "bg-pink-500/10",
      title:       "Head Motion",
      description: "Detects unnatural head movements and pose physics inconsistencies.",
      weight:      weights.headmotion,
    },
  ];

  const scoreData = [
    { key: "face",       val: sig.face_score,       details: (sig.details?.face as Record<string, unknown>) ?? {} },
    { key: "voice",      val: sig.voice_score,      details: (sig.details?.voice as Record<string, unknown>) ?? {} },
    { key: "lipsync",    val: sig.lipsync_score,    details: (sig.details?.lipsync as Record<string, unknown>) ?? {} },
    { key: "blink",      val: sig.blink_score,      details: (sig.details?.blink as Record<string, unknown>) ?? {} },
    { key: "headmotion", val: sig.headmotion_score, details: (sig.details?.headmotion as Record<string, unknown>) ?? {} },
  ];

  const uncertaintyCls: Record<string, string> = {
    LOW:    "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20",
    MEDIUM: "bg-amber-400/10 text-amber-600 border border-amber-400/20",
    HIGH:   "bg-rose-500/10 text-rose-600 border border-rose-500/20",
  };

  const videoMetadata = sig.details?.metadata as Record<string, unknown> | null | undefined;

  return (
    <div className="container max-w-5xl mx-auto py-8 px-4 space-y-8">

      {/* Back + share */}
      <div className="flex items-center justify-between">
        <Link href="/dashboard" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="w-4 h-4" /> Dashboard
        </Link>
        <button
          onClick={() => {
            navigator.clipboard.writeText(`${window.location.origin}/share/${result.id}`);
            toast.success("Share link copied!");
          }}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <Share2 className="w-4 h-4" /> Share
        </button>
      </div>

      {/* Title */}
      <div className="space-y-1">
        <h1 className="text-xl font-bold tracking-tight">Analysis Results</h1>
        <p className="text-sm text-muted-foreground truncate max-w-md">{result.video_name}</p>
      </div>

      {/* Hero row: video + gauge + verdict + meta */}
      <div className="grid md:grid-cols-3 gap-4">

        {/* Video player */}
        <div className="rounded-2xl border bg-card overflow-hidden">
          <video
            src={getVideoStreamUrl(result.video_id)}
            controls
            className="w-full h-full object-cover"
            style={{ maxHeight: "280px" }}
          />
          <div className="px-4 py-2 border-t flex items-center gap-2">
            <VerdictBadge verdict={result.verdict as Verdict} size="sm" />
            <span className="text-xs text-muted-foreground truncate">{result.video_name}</span>
          </div>
        </div>

        {/* Gauge + stats */}
        <div className="rounded-2xl border bg-card p-6 flex flex-col items-center gap-4">
          <TrustScoreGauge score={result.trust_score} size={150} />
          <VerdictBadge verdict={result.verdict as Verdict} size="lg" />
          <div className="w-full space-y-2 pt-1">
            {[
              { label: "Fake probability",  val: `${result.fake_probability.toFixed(1)}%` },
              { label: "Calibrated",        val: `${(result.confidence_calibrated_probability ?? result.fake_probability).toFixed(1)}%` },
              { label: "Confidence",        val: `${(result.confidence * 100).toFixed(0)}%` },
              ...(result.entropy != null ? [{ label: "Entropy", val: result.entropy.toFixed(3) }] : []),
            ].map(({ label, val }) => (
              <div key={label} className="flex justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-semibold tabular-nums">{val}</span>
              </div>
            ))}
          </div>
          {result.uncertainty_flag && (
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium w-full text-center ${uncertaintyCls[result.uncertainty_flag] ?? ""}`}>
              {result.uncertainty_flag === "LOW" ? "Low uncertainty" : result.uncertainty_flag === "MEDIUM" ? "Medium uncertainty" : "High uncertainty"}
            </span>
          )}
        </div>

        {/* Explanation + signal weights */}
        <div className="space-y-4">

          {/* Explanation */}
          {result.explanation && (
            <div className="rounded-2xl border bg-card p-5 space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Info className="w-4 h-4 text-primary" /> Why this verdict?
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{result.explanation}</p>
              {result.fusion_method && (
                <span className="inline-block text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
                  {result.fusion_method.replace(/_/g, " ")}
                </span>
              )}
            </div>
          )}

          {/* Signal weight bars */}
          {Object.keys(weights).length > 0 && (
            <div className="rounded-2xl border bg-card p-5 space-y-4">
              <p className="text-sm font-semibold">Signal Weights</p>
              <div className="space-y-3">
                {Object.entries(weights).map(([k, w]) => {
                  const score = scoreData.find((s) => s.key === k)?.val ?? null;
                  const cls   = riskCls(score);
                  return (
                    <div key={k} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-muted-foreground capitalize font-medium">{k}</span>
                        <div className="flex items-center gap-2">
                          {score !== null && (
                            <span className={`font-semibold tabular-nums ${cls.text}`}>{score.toFixed(0)}%</span>
                          )}
                          <span className="text-muted-foreground">{Math.round(w * 100)}% wt</span>
                        </div>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${score !== null ? cls.bar : "bg-muted-foreground/30"}`}
                          style={{ width: score !== null ? `${score}%` : `${w * 100}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 5 signal cards */}
      <div>
        <h2 className="text-base font-semibold mb-4">Signal Breakdown</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {signals.map((s, i) => (
            <SignalCard
              key={s.title}
              {...s}
              score={scoreData[i].val}
              details={scoreData[i].details}
            />
          ))}

          {/* Video metadata card */}
          {videoMetadata && (
            <div className="rounded-2xl border bg-card p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-muted flex items-center justify-center shrink-0">
                  <Activity className="w-4 h-4 text-muted-foreground" />
                </div>
                <p className="text-sm font-semibold">Video Metadata</p>
              </div>
              <div className="space-y-1">
                {Object.entries(videoMetadata).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs">
                    <span className="text-muted-foreground capitalize">{k.replace(/_/g, " ")}</span>
                    <span className="font-mono font-medium">{v != null ? String(v) : "—"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Blockchain */}
      <BlockchainCard blockchain={result.blockchain} />
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="container max-w-5xl mx-auto py-10 px-4 space-y-6">
          <Skeleton className="h-7 w-48 rounded-xl" />
          <div className="grid md:grid-cols-3 gap-6">
            <Skeleton className="h-72 rounded-2xl" />
            <div className="md:col-span-2 space-y-4">
              <Skeleton className="h-36 rounded-2xl" />
              <Skeleton className="h-28 rounded-2xl" />
            </div>
          </div>
        </div>
      }
    >
      <ResultsContent />
    </Suspense>
  );
}

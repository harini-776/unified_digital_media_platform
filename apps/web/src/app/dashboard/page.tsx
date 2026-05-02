"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getVideos } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Film, Search, ChevronLeft, ChevronRight, Upload, Clock, HardDrive, FileVideo } from "lucide-react";
import { formatBytes, formatDuration } from "@/lib/utils";
import Link from "next/link";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-5">
      <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
        <FileVideo className="w-8 h-8 text-primary" />
      </div>
      <div className="text-center">
        <p className="text-lg font-semibold">No videos yet</p>
        <p className="text-sm text-muted-foreground mt-1">Upload your first video to start detecting deepfakes.</p>
      </div>
      <Link href="/upload">
        <button className="inline-flex items-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors">
          <Upload className="w-4 h-4" /> Upload Video
        </button>
      </Link>
    </div>
  );
}

function VideoRowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-5 py-4 border-b border-border last:border-0">
      <Skeleton className="w-10 h-10 rounded-xl shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-3 w-32" />
      </div>
      <Skeleton className="h-6 w-16 rounded-full" />
    </div>
  );
}

export default function DashboardPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const perPage = 12;

  const { data, isLoading } = useQuery({
    queryKey: ["videos", page, search],
    queryFn: () => getVideos(page, perPage, search || undefined),
  });

  const totalPages = data ? Math.ceil(data.total / perPage) : 0;

  return (
    <div className="container max-w-4xl mx-auto py-10 px-4 space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {data ? `${data.total} video${data.total !== 1 ? "s" : ""} analysed` : "All uploaded videos"}
          </p>
        </div>
        <Link href="/upload">
          <button className="inline-flex items-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 rounded-lg text-sm font-medium transition-colors shrink-0">
            <Upload className="w-4 h-4" /> Upload Video
          </button>
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          placeholder="Search by filename…"
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border bg-card text-sm focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground/60"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        />
      </div>

      {/* Table card */}
      <div className="rounded-2xl border bg-card overflow-hidden shadow-sm">

        {/* Column headers */}
        <div className="grid grid-cols-[1fr_auto_auto] gap-4 px-5 py-3 border-b bg-muted/40">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">File</span>
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Size</span>
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Date</span>
        </div>

        {isLoading ? (
          <div>
            {Array.from({ length: 6 }).map((_, i) => <VideoRowSkeleton key={i} />)}
          </div>
        ) : data && data.videos.length > 0 ? (
          <div>
            {data.videos.map((video, idx) => {
              const ext = video.mime_type.split("/")[1]?.toUpperCase() ?? "VIDEO";
              const date = new Date(video.created_at);
              const isToday = new Date().toDateString() === date.toDateString();
              const displayDate = isToday
                ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                : date.toLocaleDateString([], { month: "short", day: "numeric" });

              return (
                <Link key={video.id} href={`/results?video_id=${video.id}`}>
                  <div className={`
                    grid grid-cols-[1fr_auto_auto] gap-4 items-center px-5 py-4 cursor-pointer
                    transition-colors hover:bg-accent/50
                    ${idx < data.videos.length - 1 ? "border-b border-border" : ""}
                  `}>
                    {/* File info */}
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <Film className="w-5 h-5 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{video.original_name}</p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-muted-foreground/70 bg-muted px-1.5 py-0.5 rounded font-mono">{ext}</span>
                          {video.duration_seconds && (
                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatDuration(video.duration_seconds)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Size */}
                    <span className="text-xs text-muted-foreground flex items-center gap-1 justify-end">
                      <HardDrive className="w-3 h-3 shrink-0" />
                      {formatBytes(video.file_size)}
                    </span>

                    {/* Date */}
                    <span className="text-xs text-muted-foreground text-right w-16">{displayDate}</span>
                  </div>
                </Link>
              );
            })}
          </div>
        ) : (
          <EmptyState />
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, data?.total ?? 0)} of {data?.total ?? 0}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="w-8 h-8 flex items-center justify-center rounded-lg border bg-card hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const p = Math.max(1, Math.min(page - 2, totalPages - 4)) + i;
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-8 h-8 flex items-center justify-center rounded-lg border text-xs font-medium transition-colors ${
                    p === page
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-card hover:bg-accent"
                  }`}
                >
                  {p}
                </button>
              );
            })}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="w-8 h-8 flex items-center justify-center rounded-lg border bg-card hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

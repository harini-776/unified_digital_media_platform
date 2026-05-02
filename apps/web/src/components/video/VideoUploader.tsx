"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Upload, Film, X, Loader2 } from "lucide-react";
import { cn, formatBytes } from "@/lib/utils";
import { uploadVideo } from "@/lib/api";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

const ACCEPTED = ".mp4,.mov,.avi,.webm,.mkv";
const MAX_SIZE = 500 * 1024 * 1024;

export function VideoUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const router = useRouter();

  const validate = (f: File): boolean => {
    const ext = f.name.toLowerCase().split(".").pop() ?? "";
    if (!["mp4", "mov", "avi", "webm", "mkv"].includes(ext)) {
      toast.error("Unsupported format. Use MP4, MOV, AVI, WebM, or MKV.");
      return false;
    }
    if (f.size > MAX_SIZE) {
      toast.error("File too large. Maximum is 500MB.");
      return false;
    }
    return true;
  };

  const pick = (f: File | null | undefined) => {
    if (f && validate(f)) setFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setUploadProgress(10);
    try {
      const timer = setInterval(() => {
        setUploadProgress((p) => Math.min(p + 5, 85));
      }, 300);
      const result = await uploadVideo(file);
      clearInterval(timer);
      setUploadProgress(100);
      toast.success("Upload successful! Analysis started.");
      router.push(`/results?job_id=${result.job_id}&video_id=${result.video_id}`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
      setUploadProgress(0);
    }
  };

  if (file) {
    return (
      <Card>
        <CardContent className="py-6 space-y-4">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-lg bg-primary/10 shrink-0">
              <Film className="w-6 h-6 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">{file.name}</p>
              <p className="text-sm text-muted-foreground">{formatBytes(file.size)}</p>
            </div>
            {!uploading && (
              <button
                onClick={() => setFile(null)}
                className="p-2 rounded hover:bg-muted transition-colors"
                aria-label="Remove file"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {uploading ? (
            <>
              <Progress value={uploadProgress} />
              <p className="text-sm text-muted-foreground text-center">
                {uploadProgress < 85 ? "Uploading..." : uploadProgress < 100 ? "Processing..." : "Done!"}
              </p>
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Analyzing for deepfake signals...
              </div>
            </>
          ) : (
            <button
              onClick={handleUpload}
              className="w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2 rounded-md font-medium text-sm transition-colors"
            >
              <Upload className="w-4 h-4" />
              Analyze Video
            </button>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <div
      className={cn(
        "relative border-2 border-dashed rounded-lg transition-all bg-card",
        dragActive ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50"
      )}
      onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragActive(true); }}
      onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); }}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        pick(e.dataTransfer.files?.[0]);
      }}
    >
      {/*
        The input covers the entire dropzone at opacity-0.
        Any click anywhere on the card hits this input and opens the OS file picker.
        No JavaScript click() calls needed — pure HTML behaviour.
      */}
      <input
        type="file"
        accept={ACCEPTED}
        onChange={(e) => {
          pick(e.target.files?.[0]);
          e.target.value = "";
        }}
        title=""
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          opacity: 0,
          cursor: "pointer",
          zIndex: 10,
        }}
      />

      {/* Visual content — pointer-events-none so clicks pass through to the input above */}
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center pointer-events-none select-none">
        <div className="p-4 rounded-full bg-primary/10 mb-4">
          <Upload className="w-8 h-8 text-primary" />
        </div>
        <p className="text-lg font-medium mb-1">
          {dragActive ? "Drop your video here" : "Drag & drop a video file"}
        </p>
        <p className="text-sm text-muted-foreground mb-4">
          or click anywhere to browse local files
        </p>
        <span className="inline-flex items-center px-4 py-2 rounded-md border border-input bg-background text-sm font-medium shadow-sm">
          Browse Files
        </span>
      </div>
    </div>
  );
}

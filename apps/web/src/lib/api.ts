import axios, { AxiosError } from "axios";
import { toast } from "sonner";
import type {
  VideoUploadResponse,
  JobStatus,
  AnalysisResult,
  VideoListResponse,
} from "@/types";
import { clearSession, getToken } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PREFIX = "/api/v1";

const api = axios.create({ baseURL: API_BASE });

// ── Request: attach Bearer token if we have one ──────────────────────────────
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response: surface auth/rate-limit errors as toasts; redirect on 401 ──────
//
// 401: token missing/expired/invalid → clear session and redirect to /login.
// 403: authenticated but forbidden (admin-only routes) → show toast, no redirect.
// 429: rate-limited → show toast with the API's detail message.
//
// Note: ownership-mismatch IDOR returns *404* by design (see app/core/deps.py
// assert_video_owner) — we do nothing special here; the calling code should
// render its own "not found" UI.
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (status === 401) {
      clearSession();
      if (typeof window !== "undefined") {
        const onLoginPage = window.location.pathname.startsWith("/login");
        const onRegisterPage = window.location.pathname.startsWith("/register");
        if (!onLoginPage && !onRegisterPage) {
          // Preserve the page the user was trying to reach.
          const next = encodeURIComponent(window.location.pathname + window.location.search);
          window.location.href = `/login?next=${next}`;
        }
      }
    } else if (status === 403) {
      toast.error(typeof detail === "string" ? detail : "You don't have access to that.");
    } else if (status === 429) {
      toast.error(
        typeof detail === "string"
          ? detail
          : "You're going too fast — try again in a moment.",
      );
    }

    return Promise.reject(error);
  },
);

// ── API surface ──────────────────────────────────────────────────────────────

export async function uploadVideo(file: File): Promise<VideoUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<VideoUploadResponse>(
    `${PREFIX}/videos/upload`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await api.get<JobStatus>(`${PREFIX}/jobs/${jobId}`);
  return data;
}

export async function getVideoResult(videoId: string): Promise<AnalysisResult> {
  const { data } = await api.get<AnalysisResult>(
    `${PREFIX}/videos/${videoId}/result`,
  );
  return data;
}

export async function getVideos(
  page: number = 1,
  perPage: number = 20,
  search?: string,
): Promise<VideoListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    per_page: perPage.toString(),
  });
  if (search) params.set("search", search);
  const { data } = await api.get<VideoListResponse>(
    `${PREFIX}/videos?${params}`,
  );
  return data;
}

interface StreamUrlResponse {
  url: string;
  expires_in: number;
}

/**
 * Mint a short-lived signed URL the browser can hand to a <video> tag.
 *
 * <video> elements cannot send the Authorization header, so the streaming
 * endpoint validates a query-string HMAC token instead. The returned URL
 * expires (default 5 minutes); refetch if playback fails after a long pause.
 */
export async function getVideoStreamUrl(videoId: string): Promise<string> {
  const { data } = await api.get<StreamUrlResponse>(
    `${PREFIX}/videos/${videoId}/stream-url`,
  );
  // The API returns a path like /api/v1/videos/<id>/stream?token=... — prepend
  // the base so it works regardless of the page the player is on.
  return data.url.startsWith("http") ? data.url : `${API_BASE}${data.url}`;
}

export default api;

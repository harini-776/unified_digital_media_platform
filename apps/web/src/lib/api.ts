import axios from "axios";
import type {
  VideoUploadResponse,
  JobStatus,
  AnalysisResult,
  VideoListResponse,
} from "@/types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
});

const PREFIX = "/api/v1";

export async function uploadVideo(file: File): Promise<VideoUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<VideoUploadResponse>(
    `${PREFIX}/videos/upload`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await api.get<JobStatus>(`${PREFIX}/jobs/${jobId}`);
  return data;
}

export async function getVideoResult(videoId: string): Promise<AnalysisResult> {
  const { data } = await api.get<AnalysisResult>(
    `${PREFIX}/videos/${videoId}/result`
  );
  return data;
}

export async function getVideos(
  page: number = 1,
  perPage: number = 20,
  search?: string
): Promise<VideoListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    per_page: perPage.toString(),
  });
  if (search) params.set("search", search);
  const { data } = await api.get<VideoListResponse>(
    `${PREFIX}/videos?${params}`
  );
  return data;
}

export function getVideoStreamUrl(videoId: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${base}${PREFIX}/videos/${videoId}/stream`;
}

export default api;

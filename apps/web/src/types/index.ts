export type Verdict = "authentic" | "suspicious" | "manipulated";

export interface VideoUploadResponse {
  video_id: string;
  job_id: string;
  message: string;
}

export interface JobStatus {
  id: string;
  video_id: string;
  status: string;
  progress: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface SignalBreakdown {
  face_score: number | null;
  lipsync_score: number | null;
  voice_score: number | null;
  blink_score: number | null;
  headmotion_score: number | null;
  details: Record<string, unknown> | null;
}

export interface BlockchainStatus {
  verified: boolean | null;
  match: boolean | null;
  tx_hash: string | null;
  ipfs_cid: string | null;
  network: string | null;
}

export interface AnalysisResult {
  id: string;
  job_id: string;
  video_id: string;
  fake_probability: number;
  trust_score: number;
  verdict: Verdict;
  confidence: number;
  confidence_calibrated_probability: number | null;
  uncertainty_flag: "LOW" | "MEDIUM" | "HIGH" | null;
  entropy: number | null;
  explanation: string | null;
  modality_weights: Record<string, number> | null;
  fusion_method: string | null;
  signals: SignalBreakdown;
  blockchain: BlockchainStatus;
  created_at: string;
  video_name: string | null;
  share_url: string | null;
}

export interface Video {
  id: string;
  filename: string;
  original_name: string;
  file_size: number;
  mime_type: string;
  duration_seconds: number | null;
  file_hash: string;
  ipfs_cid: string | null;
  created_at: string;
}

export interface VideoListResponse {
  videos: Video[];
  total: number;
  page: number;
  per_page: number;
}

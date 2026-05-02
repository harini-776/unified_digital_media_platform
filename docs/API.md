# TrustMedia API Reference

Base URL: `http://localhost:8000/api/v1`

## Endpoints

### POST /videos/upload
Upload a video for deepfake analysis.

**Request**: `multipart/form-data`
- `file`: Video file (MP4, MOV, AVI, WebM, MKV; max 500MB)

**Response** `200`:
```json
{
  "video_id": "uuid",
  "job_id": "uuid",
  "message": "Upload successful. Analysis started."
}
```

### GET /jobs/{job_id}
Get analysis job status and progress.

**Response** `200`:
```json
{
  "id": "uuid",
  "video_id": "uuid",
  "status": "processing",
  "progress": 45,
  "error_message": null,
  "started_at": "2024-01-01T00:00:00",
  "completed_at": null,
  "created_at": "2024-01-01T00:00:00"
}
```

Status values: `pending`, `processing`, `extracting`, `analyzing`, `blockchain_check`, `completed`, `failed`

### GET /videos/{video_id}/result
Get the analysis result for a video.

**Response** `200`:
```json
{
  "id": "uuid",
  "job_id": "uuid",
  "video_id": "uuid",
  "fake_probability": 23.5,
  "trust_score": 77,
  "verdict": "authentic",
  "confidence": 0.85,
  "signals": {
    "face_score": 15.2,
    "voice_score": 30.0,
    "lipsync_score": 25.0,
    "blink_score": 18.5,
    "details": { ... }
  },
  "blockchain": {
    "verified": true,
    "match": true,
    "tx_hash": "0x...",
    "ipfs_cid": "Qm...",
    "network": "polygon-amoy"
  },
  "created_at": "2024-01-01T00:00:00",
  "video_name": "interview.mp4",
  "share_url": "/share/uuid"
}
```

### GET /videos
List all uploaded videos.

**Query params**: `page` (default 1), `per_page` (default 20), `search`

### POST /blockchain/register
Register media provenance on blockchain.

**Request**:
```json
{
  "video_hash": "sha256-hex",
  "cid": "IPFS-CID",
  "owner_address": "0x...",
  "device_signature": "optional"
}
```

### POST /blockchain/verify
Verify media against blockchain record.

**Request**:
```json
{
  "video_hash": "sha256-hex"
}
```

## Interactive Docs
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

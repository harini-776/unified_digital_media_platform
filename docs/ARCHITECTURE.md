# TrustMedia - Architecture

## System Overview

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   Next.js    │────▶│   FastAPI API    │────▶│  Celery Worker   │
│   Frontend   │◀────│   (Port 8000)   │◀────│  (Background)    │
│  (Port 3000) │     └────────┬────────┘     └────────┬─────────┘
└──────────────┘              │                        │
                              │                        │
                    ┌─────────▼────────┐     ┌────────▼─────────┐
                    │   PostgreSQL     │     │   AI Pipeline    │
                    │   (Port 5432)    │     │                  │
                    └──────────────────┘     │ ┌──────────────┐ │
                                            │ │ Face Detect  │ │
                    ┌──────────────────┐     │ │ Voice Embed  │ │
                    │   Redis          │     │ │ Lip Sync     │ │
                    │   (Port 6379)    │     │ │ Blink/Motion │ │
                    └──────────────────┘     │ └──────────────┘ │
                                            │ ┌──────────────┐ │
                    ┌──────────────────┐     │ │   Fusion     │ │
                    │   Blockchain     │     │ └──────────────┘ │
                    │   (Polygon)      │     └──────────────────┘
                    └──────────────────┘
```

## Data Flow

1. **Upload**: User uploads video → API saves file → creates DB records → dispatches Celery task
2. **Extract**: Worker extracts frames (FFmpeg) and audio (WAV)
3. **Analyze**: Four parallel signals: face, voice, lip-sync, blink
4. **Fuse**: Weighted fusion combines signals → fake_probability
5. **Blockchain**: Check on-chain records → override AI verdict if found
6. **Result**: Store result → client polls job status → renders results

## Decision Engine

```
IF blockchain record exists for video hash:
    IF hash matches on-chain record:
        verdict = AUTHENTIC (trust_score = 100)
    ELSE:
        verdict = MANIPULATED (trust_score = 0)
ELSE:
    run AI pipeline
    fake_probability = weighted_fusion(face, voice, lipsync, blink)
    IF fake_probability >= 70: verdict = MANIPULATED
    ELIF fake_probability >= 40: verdict = SUSPICIOUS
    ELSE: verdict = AUTHENTIC
    trust_score = 100 - fake_probability
```

## Database Schema

- **videos**: file metadata, hash, storage path, IPFS CID
- **analysis_jobs**: status tracking, progress, celery task ID
- **analysis_results**: scores, verdict, signal breakdown
- **blockchain_records**: tx hash, CID, owner, network

## Tech Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Frontend    | Next.js 14, TypeScript, Tailwind, shadcn/ui |
| API         | FastAPI, SQLAlchemy, Pydantic     |
| Workers     | Celery + Redis                    |
| Database    | PostgreSQL                        |
| AI          | PyTorch, MediaPipe, Wav2Vec2      |
| Blockchain  | Solidity, Hardhat, Ethers.js      |
| Storage     | Local filesystem / IPFS (Pinata)  |

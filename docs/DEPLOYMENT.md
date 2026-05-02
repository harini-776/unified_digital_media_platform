# TrustMedia - Deployment Guide

## Architecture Overview (Production)

```
Vercel (Frontend) ──▶ Railway/Render (API + Worker) ──▶ Managed Postgres
                                                    ──▶ Managed Redis
                                                    ──▶ Polygon Amoy (Blockchain)
                                                    ──▶ S3 / Pinata (Storage)
```

## Frontend: Deploy to Vercel

```bash
cd apps/web
npx vercel --prod
```

Set environment variables in Vercel dashboard:
- `NEXT_PUBLIC_API_URL` = your API URL (e.g., https://api.trustmedia.example.com)
- `NEXT_PUBLIC_CONTRACT_ADDRESS` = deployed contract address
- `NEXT_PUBLIC_CHAIN_ID` = 80002
- `NEXT_PUBLIC_RPC_URL` = https://rpc-amoy.polygon.technology
- `NEXT_PUBLIC_EXPLORER_URL` = https://amoy.polygonscan.com

## Backend: Deploy to Railway / Render

### Option A: Railway
1. Connect your GitHub repo
2. Create two services: `api` and `worker`
3. Add PostgreSQL and Redis add-ons
4. Set root directory to `.` (project root)
5. Set Dockerfile path to `docker/Dockerfile.api` and `docker/Dockerfile.worker`
6. Add all env vars from `.env.example`

### Option B: Docker on VM
```bash
# On your server
git clone <repo> && cd finalyear
cp services/api/.env.example services/api/.env
# Edit .env with production values
docker-compose up -d --build
```

## Environment Variables Checklist

### Required
- [ ] `DATABASE_URL` - Managed Postgres connection string
- [ ] `REDIS_URL` - Managed Redis connection string
- [ ] `CELERY_BROKER_URL` - Redis URL for Celery broker
- [ ] `CORS_ORIGINS` - Frontend URL(s)
- [ ] `JWT_SECRET` - Strong random string (32+ chars)

### Blockchain (optional but recommended)
- [ ] `RPC_URL` - Polygon RPC endpoint
- [ ] `CONTRACT_ADDRESS` - Deployed contract address
- [ ] `PRIVATE_KEY` - Deployer/signer wallet key

### Storage (optional)
- [ ] `PINATA_JWT` - For IPFS upload via Pinata

## Production Considerations

### Rate Limits
Add to FastAPI middleware:
```python
# Use slowapi or custom middleware
# Recommended: 10 uploads/min per IP, 100 API calls/min
```

### Max Upload Size
Set `MAX_UPLOAD_SIZE_MB=200` for production (or lower for demo).

### Timeouts
- API request timeout: 30s
- Celery task timeout: 600s (10 min for large videos)
- Video processing: scales with duration

### Retries
Celery tasks have `acks_late=True` so failed tasks are retried.

## Demo Mode Configuration

For showcasing without GPU:
```env
DEMO_MODE=true
MODEL_DEVICE=cpu
MAX_UPLOAD_SIZE_MB=50
```

This limits analysis to 30 frames and smaller videos.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| FFmpeg not found | Install ffmpeg: `apt install ffmpeg` |
| CUDA out of memory | Set `MODEL_DEVICE=cpu` or reduce `MODEL_BATCH_SIZE` |
| Celery not picking up tasks | Check Redis connection and queue names |
| CORS errors | Verify `CORS_ORIGINS` includes frontend URL |
| Database connection refused | Check `DATABASE_URL` and PostgreSQL status |
| Contract deploy fails | Ensure wallet has testnet MATIC |
| Upload too large | Check `MAX_UPLOAD_SIZE_MB` and nginx `client_max_body_size` |

## Future Improvements

1. **SyncNet integration** for production-grade lip-sync detection
2. **Attention-based fusion** to learn signal importance dynamically
3. **GPU inference** with batched processing for throughput
4. **IPFS pinning** for all uploaded media
5. **Webhook notifications** for job completion
6. **PDF report generation** for shareable results
7. **Multi-chain support** (Ethereum, Base, Arbitrum)
8. **User authentication** with roles (admin, analyst, viewer)
9. **Real-time WebSocket** progress updates
10. **Model fine-tuning** on domain-specific deepfake datasets

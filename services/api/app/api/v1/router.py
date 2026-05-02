from fastapi import APIRouter
from app.api.v1 import videos, jobs, results, blockchain, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(results.router, prefix="/videos", tags=["results"])
api_router.include_router(blockchain.router, prefix="/blockchain", tags=["blockchain"])

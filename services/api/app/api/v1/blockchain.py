from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.blockchain import (
    BlockchainRegisterRequest,
    BlockchainRegisterResponse,
    BlockchainVerifyRequest,
    BlockchainVerifyResponse,
)
from app.services.blockchain_service import register_on_chain, verify_on_chain, save_blockchain_record

router = APIRouter()


@router.post("/register", response_model=BlockchainRegisterResponse)
async def register_media(
    request: BlockchainRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a media hash and CID on the blockchain."""
    try:
        result = await register_on_chain(
            video_hash=request.video_hash,
            cid=request.cid,
            device_signature=request.device_signature or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Blockchain transaction failed: {str(e)}")

    await save_blockchain_record(
        db=db,
        video_hash=request.video_hash,
        cid=request.cid,
        tx_hash=result["tx_hash"],
        block_number=result.get("block_number"),
        owner_address=result["owner"],
        device_signature=request.device_signature,
    )

    return BlockchainRegisterResponse(
        tx_hash=result["tx_hash"],
        block_number=result.get("block_number"),
        network=result["network"],
    )


@router.post("/verify", response_model=BlockchainVerifyResponse)
async def verify_media(request: BlockchainVerifyRequest):
    """Verify a media hash or CID against the blockchain."""
    if not request.video_hash and not request.cid:
        raise HTTPException(400, "Provide either video_hash or cid")

    lookup_hash = request.video_hash or request.cid
    result = await verify_on_chain(lookup_hash)

    return BlockchainVerifyResponse(
        found=result["found"],
        match=result.get("match"),
        tx_hash=result.get("tx_hash"),
        owner=result.get("owner"),
        timestamp=result.get("timestamp"),
        network="polygon-amoy" if result["found"] else None,
        message=result["message"],
    )

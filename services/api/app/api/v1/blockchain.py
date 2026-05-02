from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.database import get_db
from app.core.deps import assert_video_owner, get_current_user
from app.core.limiter import limiter
from app.models.user import User
from app.models.video import Video
from app.schemas.blockchain import (
    BlockchainRegisterRequest,
    BlockchainRegisterResponse,
    BlockchainVerifyRequest,
    BlockchainVerifyResponse,
)
from app.services.blockchain_service import (
    register_on_chain,
    save_blockchain_record,
    verify_on_chain,
)

router = APIRouter()


@router.post("/register", response_model=BlockchainRegisterResponse)
@limiter.limit("5/hour")
async def register_media(
    request: Request,
    body: BlockchainRegisterRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Register a media hash and CID on the blockchain.

    Authenticated. Two cases:
      - The hash matches a Video row → must be owned by the calling user (404 otherwise).
      - The hash does not match any Video row → allowed (the user is registering
        external media), and audit-logged with target_type=external_hash.
    """
    video_match = await db.execute(
        select(Video).where(Video.file_hash == body.video_hash)
    )
    video = video_match.scalar_one_or_none()

    if video is not None:
        # Known video — caller must own it (or be admin). assert_video_owner does the check.
        await assert_video_owner(db, video.id, user)
        target_type = "video"
        target_id = video.id
    else:
        # Unknown hash — legitimate "register external media" flow. Allowed but audited.
        target_type = "external_hash"
        target_id = body.video_hash

    try:
        result = await register_on_chain(
            video_hash=body.video_hash,
            cid=body.cid,
            device_signature=body.device_signature or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Blockchain transaction failed: {str(e)}")

    await save_blockchain_record(
        db=db,
        video_hash=body.video_hash,
        cid=body.cid,
        tx_hash=result["tx_hash"],
        block_number=result.get("block_number"),
        owner_address=result["owner"],
        device_signature=body.device_signature,
    )

    audit(
        "blockchain.register",
        user_id=user.id,
        target_type=target_type,
        target_id=target_id,
        tx_hash=result["tx_hash"],
    )

    return BlockchainRegisterResponse(
        tx_hash=result["tx_hash"],
        block_number=result.get("block_number"),
        network=result["network"],
    )


@router.post("/verify", response_model=BlockchainVerifyResponse)
@limiter.limit("60/minute")
async def verify_media(request: Request, body: BlockchainVerifyRequest):
    """Public lookup: verify a media hash or CID against the blockchain."""
    if not body.video_hash and not body.cid:
        raise HTTPException(400, "Provide either video_hash or cid")

    lookup_hash = body.video_hash or body.cid
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

from pydantic import BaseModel


class BlockchainRegisterRequest(BaseModel):
    video_hash: str
    cid: str
    owner_address: str | None = None
    device_signature: str | None = None
    metadata: dict | None = None


class BlockchainRegisterResponse(BaseModel):
    tx_hash: str
    block_number: int | None = None
    network: str
    message: str = "Record registered on blockchain."


class BlockchainVerifyRequest(BaseModel):
    video_hash: str | None = None
    cid: str | None = None


class BlockchainVerifyResponse(BaseModel):
    found: bool
    match: bool | None = None
    tx_hash: str | None = None
    owner: str | None = None
    timestamp: int | None = None
    network: str | None = None
    message: str

import json
import os
from web3 import Web3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.blockchain import BlockchainRecord

settings = get_settings()

# ABI for the MediaProvenance contract
CONTRACT_ABI = [
    {
        "inputs": [
            {"name": "_videoHash", "type": "bytes32"},
            {"name": "_cid", "type": "string"},
            {"name": "_deviceSignature", "type": "string"},
        ],
        "name": "registerMedia",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "_videoHash", "type": "bytes32"}],
        "name": "getRecord",
        "outputs": [
            {"name": "cid", "type": "string"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "owner", "type": "address"},
            {"name": "deviceSignature", "type": "string"},
            {"name": "exists", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "_videoHash", "type": "bytes32"}],
        "name": "verifyMedia",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def get_web3_contract():
    if not settings.contract_address or not settings.private_key:
        return None, None, None

    w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(settings.contract_address),
        abi=CONTRACT_ABI,
    )
    account = w3.eth.account.from_key(settings.private_key)
    return w3, contract, account


async def register_on_chain(
    video_hash: str,
    cid: str,
    device_signature: str = "",
) -> dict:
    w3, contract, account = get_web3_contract()
    if not w3:
        raise ValueError("Blockchain not configured. Set CONTRACT_ADDRESS and PRIVATE_KEY.")

    video_hash_bytes = bytes.fromhex(video_hash) if len(video_hash) == 64 else Web3.keccak(text=video_hash)

    tx = contract.functions.registerMedia(
        video_hash_bytes, cid, device_signature
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    return {
        "tx_hash": receipt.transactionHash.hex(),
        "block_number": receipt.blockNumber,
        "network": "polygon-amoy",
        "owner": account.address,
    }


async def verify_on_chain(video_hash: str) -> dict:
    w3, contract, account = get_web3_contract()
    if not w3:
        return {"found": False, "message": "Blockchain not configured."}

    video_hash_bytes = bytes.fromhex(video_hash) if len(video_hash) == 64 else Web3.keccak(text=video_hash)

    try:
        result = contract.functions.getRecord(video_hash_bytes).call()
        cid, timestamp, owner, device_sig, exists = result

        if not exists:
            return {"found": False, "message": "No blockchain record found for this media."}

        return {
            "found": True,
            "match": True,
            "cid": cid,
            "timestamp": timestamp,
            "owner": owner,
            "device_signature": device_sig,
            "message": "Blockchain record found and verified.",
        }
    except Exception as e:
        return {"found": False, "message": f"Verification failed: {str(e)}"}


async def save_blockchain_record(
    db: AsyncSession,
    video_hash: str,
    cid: str,
    tx_hash: str,
    block_number: int | None,
    owner_address: str,
    device_signature: str | None = None,
) -> BlockchainRecord:
    record = BlockchainRecord(
        video_hash=video_hash,
        ipfs_cid=cid,
        tx_hash=tx_hash,
        block_number=block_number,
        owner_address=owner_address,
        device_signature=device_signature,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def find_blockchain_record(db: AsyncSession, video_hash: str) -> BlockchainRecord | None:
    result = await db.execute(
        select(BlockchainRecord).where(BlockchainRecord.video_hash == video_hash)
    )
    return result.scalar_one_or_none()

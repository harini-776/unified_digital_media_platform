const hre = require("hardhat");

async function main() {
  const CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3";
  const [owner, addr1] = await hre.ethers.getSigners();

  const contract = await hre.ethers.getContractAt("MediaProvenance", CONTRACT_ADDRESS);

  console.log("=== MediaProvenance Contract Interaction ===\n");
  console.log("Contract:", CONTRACT_ADDRESS);
  console.log("Owner:", owner.address);

  // 1. Register a media record
  const videoHash = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("sample-video-sha256-hash"));
  const cid = "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco";
  const deviceSig = "device-camera-001";

  console.log("\n--- Register Media ---");
  console.log("Video hash:", videoHash);
  console.log("CID:", cid);

  const tx = await contract.registerMedia(videoHash, cid, deviceSig);
  const receipt = await tx.wait();
  console.log("TX hash:", receipt.hash);
  console.log("Block:", receipt.blockNumber);
  console.log("Gas used:", receipt.gasUsed.toString());

  // Check event
  const event = receipt.logs[0];
  console.log("Event emitted:", event ? "yes" : "no");

  // 2. Verify the record exists
  console.log("\n--- Verify Media ---");
  const exists = await contract.verifyMedia(videoHash);
  console.log("Record exists:", exists);

  // 3. Get the full record
  console.log("\n--- Get Record ---");
  const record = await contract.getRecord(videoHash);
  console.log("CID:", record.cid);
  console.log("Timestamp:", record.timestamp.toString());
  console.log("Owner:", record.owner);
  console.log("Device Signature:", record.deviceSignature);
  console.log("Exists:", record.exists);

  // 4. Verify non-existent record
  console.log("\n--- Verify Non-existent ---");
  const fakeHash = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("non-existent"));
  const notExists = await contract.verifyMedia(fakeHash);
  console.log("Non-existent record:", notExists);

  // 5. Try duplicate registration (should fail)
  console.log("\n--- Duplicate Registration (should fail) ---");
  try {
    await contract.registerMedia(videoHash, "QmDuplicate", "");
    console.log("ERROR: Should have reverted!");
  } catch (e) {
    console.log("Correctly reverted:", e.message.includes("Record already exists"));
  }

  // 6. Register from a different account
  console.log("\n--- Register from different account ---");
  const videoHash2 = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("second-video-hash"));
  const tx2 = await contract.connect(addr1).registerMedia(videoHash2, "QmSecondVideo123", "phone-002");
  await tx2.wait();
  const record2 = await contract.getRecord(videoHash2);
  console.log("Second record owner:", record2.owner);
  console.log("Matches addr1:", record2.owner === addr1.address);

  // 7. Check record count
  console.log("\n--- Record Count ---");
  const count = await contract.getRecordCount();
  console.log("Total records:", count.toString());

  console.log("\n=== All interactions successful! ===");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

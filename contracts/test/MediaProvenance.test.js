const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("MediaProvenance", function () {
  let contract;
  let owner;
  let addr1;

  const sampleHash = ethers.keccak256(ethers.toUtf8Bytes("test-video-hash"));
  const sampleCid = "QmTestCID123456789";

  beforeEach(async function () {
    [owner, addr1] = await ethers.getSigners();
    const MediaProvenance = await ethers.getContractFactory("MediaProvenance");
    contract = await MediaProvenance.deploy();
    await contract.waitForDeployment();
  });

  describe("Registration", function () {
    it("should register a new media record", async function () {
      await contract.registerMedia(sampleHash, sampleCid, "device-sig-123");

      const record = await contract.getRecord(sampleHash);
      expect(record.cid).to.equal(sampleCid);
      expect(record.owner).to.equal(owner.address);
      expect(record.exists).to.be.true;
      expect(record.deviceSignature).to.equal("device-sig-123");
    });

    it("should emit MediaRegistered event", async function () {
      await expect(contract.registerMedia(sampleHash, sampleCid, ""))
        .to.emit(contract, "MediaRegistered")
        .withArgs(sampleHash, sampleCid, owner.address, await getBlockTimestamp());
    });

    it("should reject duplicate registration", async function () {
      await contract.registerMedia(sampleHash, sampleCid, "");
      await expect(
        contract.registerMedia(sampleHash, sampleCid, "")
      ).to.be.revertedWith("Record already exists");
    });

    it("should reject empty CID", async function () {
      await expect(
        contract.registerMedia(sampleHash, "", "")
      ).to.be.revertedWith("CID cannot be empty");
    });
  });

  describe("Verification", function () {
    it("should verify existing record", async function () {
      await contract.registerMedia(sampleHash, sampleCid, "");
      expect(await contract.verifyMedia(sampleHash)).to.be.true;
    });

    it("should return false for non-existent record", async function () {
      const fakeHash = ethers.keccak256(ethers.toUtf8Bytes("non-existent"));
      expect(await contract.verifyMedia(fakeHash)).to.be.false;
    });
  });

  describe("Record count", function () {
    it("should track record count", async function () {
      expect(await contract.getRecordCount()).to.equal(0);
      await contract.registerMedia(sampleHash, sampleCid, "");
      expect(await contract.getRecordCount()).to.equal(1);
    });
  });
});

async function getBlockTimestamp() {
  const block = await ethers.provider.getBlock("latest");
  return block.timestamp + 1; // next block
}

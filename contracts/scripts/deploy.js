const hre = require("hardhat");

async function main() {
  console.log("Deploying MediaProvenance contract...");

  const MediaProvenance = await hre.ethers.getContractFactory("MediaProvenance");
  const contract = await MediaProvenance.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log(`MediaProvenance deployed to: ${address}`);
  console.log(`Network: ${hre.network.name}`);
  console.log("\nUpdate your .env files:");
  console.log(`CONTRACT_ADDRESS=${address}`);
  console.log(`NEXT_PUBLIC_CONTRACT_ADDRESS=${address}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

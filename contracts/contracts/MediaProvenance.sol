// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MediaProvenance
 * @notice Stores and verifies media provenance records on-chain.
 * Each record links a video hash to an IPFS CID, timestamp, and owner.
 */
contract MediaProvenance {
    struct MediaRecord {
        string cid;
        uint256 timestamp;
        address owner;
        string deviceSignature;
        bool exists;
    }

    mapping(bytes32 => MediaRecord) private records;

    // Track all registered hashes for enumeration
    bytes32[] private registeredHashes;

    event MediaRegistered(
        bytes32 indexed videoHash,
        string cid,
        address indexed owner,
        uint256 timestamp
    );

    /**
     * @notice Register a new media record.
     * @param _videoHash SHA-256 hash of the video file.
     * @param _cid IPFS Content Identifier.
     * @param _deviceSignature Optional device/camera signature.
     */
    function registerMedia(
        bytes32 _videoHash,
        string calldata _cid,
        string calldata _deviceSignature
    ) external {
        require(!records[_videoHash].exists, "Record already exists");
        require(bytes(_cid).length > 0, "CID cannot be empty");

        records[_videoHash] = MediaRecord({
            cid: _cid,
            timestamp: block.timestamp,
            owner: msg.sender,
            deviceSignature: _deviceSignature,
            exists: true
        });

        registeredHashes.push(_videoHash);

        emit MediaRegistered(_videoHash, _cid, msg.sender, block.timestamp);
    }

    /**
     * @notice Retrieve a media record by its hash.
     */
    function getRecord(bytes32 _videoHash)
        external
        view
        returns (
            string memory cid,
            uint256 timestamp,
            address owner,
            string memory deviceSignature,
            bool exists
        )
    {
        MediaRecord storage record = records[_videoHash];
        return (
            record.cid,
            record.timestamp,
            record.owner,
            record.deviceSignature,
            record.exists
        );
    }

    /**
     * @notice Check if a media record exists for the given hash.
     */
    function verifyMedia(bytes32 _videoHash) external view returns (bool) {
        return records[_videoHash].exists;
    }

    /**
     * @notice Get the total number of registered media records.
     */
    function getRecordCount() external view returns (uint256) {
        return registeredHashes.length;
    }
}

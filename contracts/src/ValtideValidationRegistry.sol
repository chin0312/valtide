// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title ValtideValidationRegistry
/// @notice Stores the latest authorized Valtide validation attestation for an
///         asset and reference pair.
/// @dev The Registry stores offchain evidence; it does not run the quant model
///      or determine a consuming protocol's policy.
contract ValtideValidationRegistry is Ownable {
    enum EvidenceState {
        SUPPORTED,
        INCONCLUSIVE,
        CHALLENGED
    }

    struct ValidationAttestation {
        bytes32 referenceId;
        uint256 referencePriceE8;

        uint256 fairValueE8;
        uint256 lowerBoundE8;
        uint256 upperBoundE8;

        int32 referenceDeviationBps;
        EvidenceState evidenceState;

        bytes32 evidenceHash;
        bytes32 modelVersion;

        uint64 observedAt;
        uint64 publishedAt;
        uint64 validUntil;
    }

    mapping(bytes32 assetId => mapping(bytes32 referenceId => ValidationAttestation)) private _latestValidation;
    mapping(bytes32 assetId => mapping(bytes32 referenceId => bool)) private _hasAttestation;
    mapping(address publisher => bool) public isPublisher;

    error InvalidIdentifier();
    error InvalidPrice();
    error InvalidBounds();
    error InvalidEvidenceHash();
    error InvalidModelVersion();
    error InvalidObservedAt();
    error InvalidValidityWindow();
    error UnauthorizedPublisher(address caller);
    error ZeroAddress();

    event PublisherAuthorizationUpdated(address indexed publisher, bool authorized);
    event ValidationUpdated(
        bytes32 indexed assetId,
        bytes32 indexed referenceId,
        EvidenceState evidenceState,
        uint64 observedAt,
        uint64 publishedAt,
        uint64 validUntil,
        bytes32 evidenceHash,
        bytes32 modelVersion
    );

    constructor(address initialOwner) Ownable(initialOwner) {}

    /// @notice Authorize or revoke an address that may publish attestations.
    function setPublisher(address publisher, bool authorized) external onlyOwner {
        if (publisher == address(0)) revert ZeroAddress();

        isPublisher[publisher] = authorized;
        emit PublisherAuthorizationUpdated(publisher, authorized);
    }

    /// @notice Publish the latest attestation for an asset/reference pair.
    /// @dev `publishedAt` is always assigned by this contract.
    function publishValidation(bytes32 assetId, ValidationAttestation calldata input) external {
        if (!isPublisher[msg.sender]) revert UnauthorizedPublisher(msg.sender);
        _validateInput(assetId, input);

        ValidationAttestation memory attestation = input;
        attestation.publishedAt = uint64(block.timestamp);

        _latestValidation[assetId][input.referenceId] = attestation;
        _hasAttestation[assetId][input.referenceId] = true;

        emit ValidationUpdated(
            assetId,
            input.referenceId,
            input.evidenceState,
            input.observedAt,
            attestation.publishedAt,
            input.validUntil,
            input.evidenceHash,
            input.modelVersion
        );
    }

    /// @notice Return the latest attestation and whether the pair has been published.
    function getLatest(bytes32 assetId, bytes32 referenceId)
        external
        view
        returns (ValidationAttestation memory attestation, bool exists)
    {
        return (_latestValidation[assetId][referenceId], _hasAttestation[assetId][referenceId]);
    }

    /// @notice Return whether an attestation has ever been published for the pair.
    function hasAttestation(bytes32 assetId, bytes32 referenceId) external view returns (bool) {
        return _hasAttestation[assetId][referenceId];
    }

    /// @notice Return whether the latest attestation is within its published validity window.
    function isFresh(bytes32 assetId, bytes32 referenceId) external view returns (bool) {
        return
            _hasAttestation[assetId][referenceId]
                && block.timestamp <= _latestValidation[assetId][referenceId].validUntil;
    }

    function _validateInput(bytes32 assetId, ValidationAttestation calldata input) internal view {
        if (assetId == bytes32(0) || input.referenceId == bytes32(0)) {
            revert InvalidIdentifier();
        }
        if (input.referencePriceE8 == 0 || input.fairValueE8 == 0) revert InvalidPrice();
        if (input.lowerBoundE8 > input.upperBoundE8) revert InvalidBounds();
        if (input.evidenceHash == bytes32(0)) revert InvalidEvidenceHash();
        if (input.modelVersion == bytes32(0)) revert InvalidModelVersion();
        if (input.observedAt == 0 || input.observedAt > block.timestamp) {
            revert InvalidObservedAt();
        }
        if (input.validUntil <= input.observedAt || input.validUntil <= block.timestamp) {
            revert InvalidValidityWindow();
        }
    }
}

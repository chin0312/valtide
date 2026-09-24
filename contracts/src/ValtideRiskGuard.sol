// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ValtideValidationRegistry} from "./ValtideValidationRegistry.sol";

/// @title ValtideRiskGuard
/// @notice Evaluates a policy owned by a consuming application against the
///         Evidence State stored in a ValtideValidationRegistry.
/// @dev The Guard does not change evidence and does not enforce consumer
///      behavior. The consuming application remains responsible for enforcement.
contract ValtideRiskGuard {
    enum PolicyAction {
        ALLOW,
        MONITOR,
        REQUIRE_REVIEW,
        RESTRICT_NEW_RISK
    }

    struct ValidationPolicy {
        uint64 maxAge;

        PolicyAction onSupported;
        PolicyAction onInconclusive;
        PolicyAction onChallenged;
        PolicyAction onStale;
    }

    address public immutable registry;

    mapping(address policyOwner => mapping(bytes32 assetId => mapping(bytes32 referenceId => ValidationPolicy))) private
        _policies;
    mapping(address policyOwner => mapping(bytes32 assetId => mapping(bytes32 referenceId => bool))) private
        _policyConfigured;

    error InvalidRegistry();
    error InvalidIdentifier();
    error InvalidMaxAge();
    error PolicyNotConfigured(address policyOwner, bytes32 assetId, bytes32 referenceId);

    event PolicyUpdated(
        address indexed policyOwner,
        bytes32 indexed assetId,
        bytes32 indexed referenceId,
        uint64 maxAge,
        PolicyAction onSupported,
        PolicyAction onInconclusive,
        PolicyAction onChallenged,
        PolicyAction onStale
    );

    constructor(address registry_) {
        if (registry_ == address(0)) revert InvalidRegistry();
        registry = registry_;
    }

    /// @notice Configure the caller's policy for one asset/reference pair.
    /// @dev A policy owner is the consuming application address, not the Registry publisher.
    function setPolicy(bytes32 assetId, bytes32 referenceId, ValidationPolicy calldata policy) external {
        if (assetId == bytes32(0) || referenceId == bytes32(0)) {
            revert InvalidIdentifier();
        }
        if (policy.maxAge == 0) revert InvalidMaxAge();

        _policies[msg.sender][assetId][referenceId] = policy;
        _policyConfigured[msg.sender][assetId][referenceId] = true;

        emit PolicyUpdated(
            msg.sender,
            assetId,
            referenceId,
            policy.maxAge,
            policy.onSupported,
            policy.onInconclusive,
            policy.onChallenged,
            policy.onStale
        );
    }

    /// @notice Read a policy and whether it has been configured.
    function getPolicy(address policyOwner, bytes32 assetId, bytes32 referenceId)
        external
        view
        returns (ValidationPolicy memory policy, bool configured)
    {
        return (_policies[policyOwner][assetId][referenceId], _policyConfigured[policyOwner][assetId][referenceId]);
    }

    /// @notice Evaluate the caller's policy as the consuming application.
    function evaluate(bytes32 assetId, bytes32 referenceId)
        external
        view
        returns (
            ValtideValidationRegistry.EvidenceState evidenceState,
            PolicyAction policyAction,
            bool exists,
            bool fresh
        )
    {
        return evaluateFor(msg.sender, assetId, referenceId);
    }

    /// @notice Inspect another policy owner's evaluation without changing state.
    function evaluateFor(address policyOwner, bytes32 assetId, bytes32 referenceId)
        public
        view
        returns (
            ValtideValidationRegistry.EvidenceState evidenceState,
            PolicyAction policyAction,
            bool exists,
            bool fresh
        )
    {
        if (!_policyConfigured[policyOwner][assetId][referenceId]) {
            revert PolicyNotConfigured(policyOwner, assetId, referenceId);
        }

        ValidationPolicy memory policy = _policies[policyOwner][assetId][referenceId];
        (ValtideValidationRegistry.ValidationAttestation memory attestation, bool attestationExists) =
            ValtideValidationRegistry(registry).getLatest(assetId, referenceId);

        // There is no fourth Evidence State for "missing". INCONCLUSIVE is a
        // safe non-SUPPORTED sentinel only; exists=false is the authoritative
        // signal that no attestation has been published.
        if (!attestationExists) {
            return (ValtideValidationRegistry.EvidenceState.INCONCLUSIVE, policy.onStale, false, false);
        }

        if (!_isFresh(attestation, policy.maxAge)) {
            return (attestation.evidenceState, policy.onStale, true, false);
        }

        return (attestation.evidenceState, _actionFor(attestation.evidenceState, policy), true, true);
    }

    function _isFresh(ValtideValidationRegistry.ValidationAttestation memory attestation, uint64 maxAge)
        internal
        view
        returns (bool)
    {
        if (block.timestamp > attestation.validUntil) return false;
        if (block.timestamp > attestation.observedAt) {
            if (block.timestamp - uint256(attestation.observedAt) > uint256(maxAge)) {
                return false;
            }
        }
        return true;
    }

    function _actionFor(ValtideValidationRegistry.EvidenceState evidenceState, ValidationPolicy memory policy)
        internal
        pure
        returns (PolicyAction)
    {
        if (evidenceState == ValtideValidationRegistry.EvidenceState.SUPPORTED) {
            return policy.onSupported;
        }
        if (evidenceState == ValtideValidationRegistry.EvidenceState.INCONCLUSIVE) {
            return policy.onInconclusive;
        }
        return policy.onChallenged;
    }
}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

import {ValtideRiskGuard} from "./ValtideRiskGuard.sol";
import {ValtideValidationRegistry} from "./ValtideValidationRegistry.sol";

/// @title DemoCollateralVault
/// @notice Minimal reference consumer demonstrating policy-aware new-exposure
///         gating. It does not custody funds or implement lending.
contract DemoCollateralVault is Ownable {
    ValtideRiskGuard public immutable riskGuard;
    bytes32 public immutable assetId;
    bytes32 public immutable referenceId;

    error InvalidDependency();
    error InvalidAmount();
    error NewExposureNotAllowed(
        ValtideValidationRegistry.EvidenceState evidenceState,
        ValtideRiskGuard.PolicyAction policyAction,
        bool exists,
        bool fresh
    );

    event PolicyConfigured(bytes32 indexed assetId, bytes32 indexed referenceId);
    event ExposureRequested(
        address indexed user,
        uint256 amount,
        ValtideValidationRegistry.EvidenceState evidenceState,
        ValtideRiskGuard.PolicyAction policyAction,
        bool exists,
        bool fresh
    );

    constructor(address initialOwner, address riskGuard_, bytes32 assetId_, bytes32 referenceId_)
        Ownable(initialOwner)
    {
        if (riskGuard_ == address(0) || assetId_ == bytes32(0) || referenceId_ == bytes32(0)) {
            revert InvalidDependency();
        }

        riskGuard = ValtideRiskGuard(riskGuard_);
        assetId = assetId_;
        referenceId = referenceId_;
    }

    /// @notice Configure the policy stored under this vault's address.
    function configurePolicy(ValtideRiskGuard.ValidationPolicy calldata policy) external onlyOwner {
        riskGuard.setPolicy(assetId, referenceId, policy);
        emit PolicyConfigured(assetId, referenceId);
    }

    /// @notice Request demo-only new exposure; no funds or balances are changed.
    function requestNewExposure(uint256 amount) external returns (ValtideRiskGuard.PolicyAction policyAction) {
        if (amount == 0) revert InvalidAmount();

        (
            ValtideValidationRegistry.EvidenceState evidenceState,
            ValtideRiskGuard.PolicyAction action,
            bool exists,
            bool fresh
        ) = riskGuard.evaluate(assetId, referenceId);

        if (action != ValtideRiskGuard.PolicyAction.ALLOW && action != ValtideRiskGuard.PolicyAction.MONITOR) {
            revert NewExposureNotAllowed(evidenceState, action, exists, fresh);
        }

        emit ExposureRequested(msg.sender, amount, evidenceState, action, exists, fresh);
        return action;
    }
}

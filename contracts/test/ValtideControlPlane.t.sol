// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

import {DemoCollateralVault} from "../src/DemoCollateralVault.sol";
import {ValtideRiskGuard} from "../src/ValtideRiskGuard.sol";
import {ValtideValidationRegistry} from "../src/ValtideValidationRegistry.sol";

contract ValtideControlPlaneTest is Test {
    ValtideValidationRegistry internal registry;
    ValtideRiskGuard internal riskGuard;
    DemoCollateralVault internal vault;

    address internal owner;
    address internal publisher;
    address internal secondPublisher;
    address internal policyOwnerA;
    address internal policyOwnerB;
    address internal user;

    bytes32 internal constant ASSET_ID = keccak256(bytes("NVDAx"));
    bytes32 internal constant REFERENCE_ID = keccak256(bytes("OKX_NVDA_USD_INDEX"));
    bytes32 internal constant OTHER_REFERENCE_ID = keccak256(bytes("CHAINLINK_NVDA"));

    function setUp() public {
        vm.warp(1_000_000);

        owner = makeAddr("owner");
        publisher = makeAddr("publisher");
        secondPublisher = makeAddr("secondPublisher");
        policyOwnerA = makeAddr("policyOwnerA");
        policyOwnerB = makeAddr("policyOwnerB");
        user = makeAddr("user");

        registry = new ValtideValidationRegistry(owner);
        riskGuard = new ValtideRiskGuard(address(registry));
        vault = new DemoCollateralVault(owner, address(riskGuard), ASSET_ID, REFERENCE_ID);

        vm.prank(owner);
        registry.setPublisher(publisher, true);

        vm.prank(owner);
        vault.configurePolicy(_defaultVaultPolicy());
    }

    // ---------------------------------------------------------------------
    // Registry
    // ---------------------------------------------------------------------

    function testOnlyAuthorizedPublisherCanPublish() public {
        ValtideValidationRegistry.ValidationInput memory attestation = _attestation(
            ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp - 60, block.timestamp + 900
        );

        vm.expectRevert(abi.encodeWithSelector(ValtideValidationRegistry.UnauthorizedPublisher.selector, address(this)));
        registry.publishValidation(ASSET_ID, attestation);

        vm.prank(publisher);
        registry.publishValidation(ASSET_ID, attestation);
        assertTrue(registry.hasAttestation(ASSET_ID, REFERENCE_ID));
    }

    function testOwnerCanAuthorizeAndRevokePublisher() public {
        ValtideValidationRegistry.ValidationInput memory attestation = _attestation(
            ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp - 60, block.timestamp + 900
        );

        vm.prank(owner);
        registry.setPublisher(secondPublisher, true);

        vm.prank(secondPublisher);
        registry.publishValidation(ASSET_ID, attestation);

        vm.prank(owner);
        registry.setPublisher(secondPublisher, false);

        vm.expectRevert(
            abi.encodeWithSelector(ValtideValidationRegistry.UnauthorizedPublisher.selector, secondPublisher)
        );
        vm.prank(secondPublisher);
        registry.publishValidation(ASSET_ID, attestation);
    }

    function testPublishedAttestationIsRetrievableAndFresh() public {
        uint64 observedAt = uint64(block.timestamp - 60);
        uint64 validUntil = uint64(block.timestamp + 900);
        ValtideValidationRegistry.ValidationInput memory attestation =
            _attestation(ValtideValidationRegistry.EvidenceState.INCONCLUSIVE, observedAt, validUntil);

        vm.prank(publisher);
        registry.publishValidation(ASSET_ID, attestation);

        (ValtideValidationRegistry.ValidationAttestation memory stored, bool exists) =
            registry.getLatest(ASSET_ID, REFERENCE_ID);

        assertTrue(exists);
        assertEq(stored.referenceId, REFERENCE_ID);
        assertEq(stored.observedAt, observedAt);
        assertEq(stored.validUntil, validUntil);
        assertEq(stored.publishedAt, uint64(block.timestamp));
        assertEq(uint8(stored.evidenceState), uint8(attestation.evidenceState));
        assertTrue(registry.isFresh(ASSET_ID, REFERENCE_ID));
    }

    function testPublishingReplacesOnlyTheMatchingAssetReferencePair() public {
        _publish(ValtideValidationRegistry.EvidenceState.SUPPORTED);

        ValtideValidationRegistry.ValidationInput memory other = _attestation(
            ValtideValidationRegistry.EvidenceState.CHALLENGED, block.timestamp - 60, block.timestamp + 900
        );
        other.referenceId = OTHER_REFERENCE_ID;
        vm.prank(publisher);
        registry.publishValidation(ASSET_ID, other);

        _publish(ValtideValidationRegistry.EvidenceState.INCONCLUSIVE);

        (ValtideValidationRegistry.ValidationAttestation memory latest, bool latestExists) =
            registry.getLatest(ASSET_ID, REFERENCE_ID);
        (ValtideValidationRegistry.ValidationAttestation memory otherStored, bool otherExists) =
            registry.getLatest(ASSET_ID, OTHER_REFERENCE_ID);

        assertTrue(latestExists);
        assertTrue(otherExists);
        assertEq(uint8(latest.evidenceState), uint8(ValtideValidationRegistry.EvidenceState.INCONCLUSIVE));
        assertEq(uint8(otherStored.evidenceState), uint8(ValtideValidationRegistry.EvidenceState.CHALLENGED));
    }

    function testUnpublishedPairIsNotARealSupportedAttestation() public view {
        (ValtideValidationRegistry.ValidationAttestation memory stored, bool exists) =
            registry.getLatest(ASSET_ID, REFERENCE_ID);

        assertFalse(exists);
        assertEq(uint8(stored.evidenceState), uint8(ValtideValidationRegistry.EvidenceState.SUPPORTED));
        assertFalse(registry.hasAttestation(ASSET_ID, REFERENCE_ID));
        assertFalse(registry.isFresh(ASSET_ID, REFERENCE_ID));
    }

    function testRegistryRejectsInvalidStructure() public {
        ValtideValidationRegistry.ValidationInput memory attestation = _attestation(
            ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp - 60, block.timestamp + 900
        );

        attestation.referencePriceE8 = 0;
        vm.expectRevert(ValtideValidationRegistry.InvalidPrice.selector);
        _publishInput(ASSET_ID, attestation);

        attestation = _attestation(
            ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp - 60, block.timestamp + 900
        );
        attestation.lowerBoundE8 = attestation.upperBoundE8 + 1;
        vm.expectRevert(ValtideValidationRegistry.InvalidBounds.selector);
        _publishInput(ASSET_ID, attestation);

        attestation = _attestation(
            ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp - 60, block.timestamp + 900
        );
        attestation.evidenceHash = bytes32(0);
        vm.expectRevert(ValtideValidationRegistry.InvalidEvidenceHash.selector);
        _publishInput(ASSET_ID, attestation);

        attestation =
            _attestation(ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp + 1, block.timestamp + 900);
        vm.expectRevert(ValtideValidationRegistry.InvalidObservedAt.selector);
        _publishInput(ASSET_ID, attestation);

        attestation =
            _attestation(ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp - 60, block.timestamp + 30);
        attestation.validUntil = attestation.observedAt;
        vm.expectRevert(ValtideValidationRegistry.InvalidValidityWindow.selector);
        _publishInput(ASSET_ID, attestation);
    }

    function testRegistryRejectsOlderObservationForSamePair() public {
        uint64 newerObservedAt = uint64(block.timestamp - 50);
        uint64 olderObservedAt = uint64(block.timestamp - 60);

        _publishInput(
            ASSET_ID,
            _attestation(ValtideValidationRegistry.EvidenceState.SUPPORTED, newerObservedAt, block.timestamp + 900)
        );

        vm.expectRevert(
            abi.encodeWithSelector(
                ValtideValidationRegistry.ObservationRollback.selector, newerObservedAt, olderObservedAt
            )
        );
        _publishInput(
            ASSET_ID,
            _attestation(ValtideValidationRegistry.EvidenceState.CHALLENGED, olderObservedAt, block.timestamp + 900)
        );
    }

    function testRegistryAllowsEqualObservationTimestampReplacement() public {
        uint64 observedAt = uint64(block.timestamp - 60);
        _publishInput(
            ASSET_ID, _attestation(ValtideValidationRegistry.EvidenceState.SUPPORTED, observedAt, block.timestamp + 900)
        );

        ValtideValidationRegistry.ValidationInput memory replacement =
            _attestation(ValtideValidationRegistry.EvidenceState.CHALLENGED, observedAt, block.timestamp + 900);
        replacement.evidenceHash = keccak256(bytes("replacement-evidence"));

        _publishInput(ASSET_ID, replacement);

        (ValtideValidationRegistry.ValidationAttestation memory stored, bool exists) =
            registry.getLatest(ASSET_ID, REFERENCE_ID);
        assertTrue(exists);
        assertEq(uint8(stored.evidenceState), uint8(ValtideValidationRegistry.EvidenceState.CHALLENGED));
        assertEq(stored.evidenceHash, replacement.evidenceHash);
        assertEq(stored.observedAt, observedAt);
    }

    function testRegistryRollbackProtectionDoesNotCrossReferencePairs() public {
        uint64 newerObservedAt = uint64(block.timestamp - 50);
        uint64 olderObservedAt = uint64(block.timestamp - 60);

        _publishInput(
            ASSET_ID,
            _attestation(ValtideValidationRegistry.EvidenceState.SUPPORTED, newerObservedAt, block.timestamp + 900)
        );

        ValtideValidationRegistry.ValidationInput memory otherPair =
            _attestation(ValtideValidationRegistry.EvidenceState.INCONCLUSIVE, olderObservedAt, block.timestamp + 900);
        otherPair.referenceId = OTHER_REFERENCE_ID;
        _publishInput(ASSET_ID, otherPair);

        (ValtideValidationRegistry.ValidationAttestation memory stored, bool exists) =
            registry.getLatest(ASSET_ID, OTHER_REFERENCE_ID);
        assertTrue(exists);
        assertEq(stored.observedAt, olderObservedAt);
        assertEq(uint8(stored.evidenceState), uint8(ValtideValidationRegistry.EvidenceState.INCONCLUSIVE));
    }

    // ---------------------------------------------------------------------
    // Risk Guard
    // ---------------------------------------------------------------------

    function testPoliciesAreIsolatedByPolicyOwner() public {
        vm.prank(policyOwnerA);
        riskGuard.setPolicy(
            ASSET_ID,
            REFERENCE_ID,
            _policy(
                15 minutes,
                ValtideRiskGuard.PolicyAction.ALLOW,
                ValtideRiskGuard.PolicyAction.MONITOR,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
            )
        );
        vm.prank(policyOwnerB);
        riskGuard.setPolicy(
            ASSET_ID,
            REFERENCE_ID,
            _policy(
                15 minutes,
                ValtideRiskGuard.PolicyAction.MONITOR,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
                ValtideRiskGuard.PolicyAction.ALLOW,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK
            )
        );

        _publish(ValtideValidationRegistry.EvidenceState.SUPPORTED);

        (, ValtideRiskGuard.PolicyAction actionA, bool existsA, bool freshA) =
            riskGuard.evaluateFor(policyOwnerA, ASSET_ID, REFERENCE_ID);
        (, ValtideRiskGuard.PolicyAction actionB, bool existsB, bool freshB) =
            riskGuard.evaluateFor(policyOwnerB, ASSET_ID, REFERENCE_ID);

        assertEq(uint8(actionA), uint8(ValtideRiskGuard.PolicyAction.ALLOW));
        assertEq(uint8(actionB), uint8(ValtideRiskGuard.PolicyAction.MONITOR));
        assertTrue(existsA);
        assertTrue(existsB);
        assertTrue(freshA);
        assertTrue(freshB);
    }

    function testEvidenceStatesMapToConfiguredActions() public {
        vm.prank(policyOwnerA);
        riskGuard.setPolicy(
            ASSET_ID,
            REFERENCE_ID,
            _policy(
                15 minutes,
                ValtideRiskGuard.PolicyAction.ALLOW,
                ValtideRiskGuard.PolicyAction.MONITOR,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
            )
        );

        _publish(ValtideValidationRegistry.EvidenceState.SUPPORTED);
        (, ValtideRiskGuard.PolicyAction supportedAction, bool supportedExists, bool supportedFresh) =
            riskGuard.evaluateFor(policyOwnerA, ASSET_ID, REFERENCE_ID);
        assertEq(uint8(supportedAction), uint8(ValtideRiskGuard.PolicyAction.ALLOW));
        assertTrue(supportedExists);
        assertTrue(supportedFresh);

        _publish(ValtideValidationRegistry.EvidenceState.INCONCLUSIVE);
        (, ValtideRiskGuard.PolicyAction inconclusiveAction, bool inconclusiveExists, bool inconclusiveFresh) =
            riskGuard.evaluateFor(policyOwnerA, ASSET_ID, REFERENCE_ID);
        assertEq(uint8(inconclusiveAction), uint8(ValtideRiskGuard.PolicyAction.MONITOR));
        assertTrue(inconclusiveExists);
        assertTrue(inconclusiveFresh);

        _publish(ValtideValidationRegistry.EvidenceState.CHALLENGED);
        (, ValtideRiskGuard.PolicyAction challengedAction, bool challengedExists, bool challengedFresh) =
            riskGuard.evaluateFor(policyOwnerA, ASSET_ID, REFERENCE_ID);
        assertEq(uint8(challengedAction), uint8(ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK));
        assertTrue(challengedExists);
        assertTrue(challengedFresh);
    }

    function testRegistryValidityMakesEvidenceStale() public {
        vm.prank(policyOwnerA);
        riskGuard.setPolicy(
            ASSET_ID,
            REFERENCE_ID,
            _policy(
                1 hours,
                ValtideRiskGuard.PolicyAction.ALLOW,
                ValtideRiskGuard.PolicyAction.MONITOR,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
            )
        );
        _publishWithWindow(
            ValtideValidationRegistry.EvidenceState.CHALLENGED, block.timestamp - 60, block.timestamp + 60
        );

        vm.warp(block.timestamp + 61);
        (
            ValtideValidationRegistry.EvidenceState evidenceState,
            ValtideRiskGuard.PolicyAction action,
            bool exists,
            bool fresh
        ) = riskGuard.evaluateFor(policyOwnerA, ASSET_ID, REFERENCE_ID);

        assertEq(uint8(evidenceState), uint8(ValtideValidationRegistry.EvidenceState.CHALLENGED));
        assertEq(uint8(action), uint8(ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW));
        assertTrue(exists);
        assertFalse(fresh);
    }

    function testPolicyMaxAgeUsesObservedAtNotPublishedAt() public {
        vm.prank(policyOwnerA);
        riskGuard.setPolicy(
            ASSET_ID,
            REFERENCE_ID,
            _policy(
                15 minutes,
                ValtideRiskGuard.PolicyAction.ALLOW,
                ValtideRiskGuard.PolicyAction.MONITOR,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
            )
        );
        _publishWithWindow(
            ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp - 1 hours, block.timestamp + 1 hours
        );

        assertTrue(registry.isFresh(ASSET_ID, REFERENCE_ID));
        (, ValtideRiskGuard.PolicyAction action, bool exists, bool fresh) =
            riskGuard.evaluateFor(policyOwnerA, ASSET_ID, REFERENCE_ID);

        assertEq(uint8(action), uint8(ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW));
        assertTrue(exists);
        assertFalse(fresh);
    }

    function testMissingAttestationUsesStalePolicyAndNeverAllowsByDefault() public {
        vm.prank(policyOwnerA);
        riskGuard.setPolicy(
            ASSET_ID,
            OTHER_REFERENCE_ID,
            _policy(
                15 minutes,
                ValtideRiskGuard.PolicyAction.ALLOW,
                ValtideRiskGuard.PolicyAction.MONITOR,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
            )
        );

        (
            ValtideValidationRegistry.EvidenceState evidenceState,
            ValtideRiskGuard.PolicyAction action,
            bool exists,
            bool fresh
        ) = riskGuard.evaluateFor(policyOwnerA, ASSET_ID, OTHER_REFERENCE_ID);

        assertEq(uint8(evidenceState), uint8(ValtideValidationRegistry.EvidenceState.INCONCLUSIVE));
        assertEq(uint8(action), uint8(ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW));
        assertFalse(exists);
        assertFalse(fresh);
    }

    function testUnconfiguredPolicyFailsExplicitly() public {
        vm.expectRevert(
            abi.encodeWithSelector(ValtideRiskGuard.PolicyNotConfigured.selector, policyOwnerA, ASSET_ID, REFERENCE_ID)
        );
        riskGuard.evaluateFor(policyOwnerA, ASSET_ID, REFERENCE_ID);
    }

    // ---------------------------------------------------------------------
    // Demo consumer
    // ---------------------------------------------------------------------

    function testSupportedPathAllowsNewExposure() public {
        _publish(ValtideValidationRegistry.EvidenceState.SUPPORTED);

        vm.prank(user);
        ValtideRiskGuard.PolicyAction action = vault.requestNewExposure(100);

        assertEq(uint8(action), uint8(ValtideRiskGuard.PolicyAction.ALLOW));
    }

    function testMissingAttestationRejectsAndReportsAbsence() public {
        vm.expectRevert(
            abi.encodeWithSelector(
                DemoCollateralVault.NewExposureNotAllowed.selector,
                ValtideValidationRegistry.EvidenceState.INCONCLUSIVE,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
                false,
                false
            )
        );
        vm.prank(user);
        vault.requestNewExposure(100);
    }

    function testInconclusivePathRequiresReview() public {
        _publish(ValtideValidationRegistry.EvidenceState.INCONCLUSIVE);

        vm.expectRevert(
            abi.encodeWithSelector(
                DemoCollateralVault.NewExposureNotAllowed.selector,
                ValtideValidationRegistry.EvidenceState.INCONCLUSIVE,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
                true,
                true
            )
        );
        vm.prank(user);
        vault.requestNewExposure(100);
    }

    function testChallengedPathRestrictsNewRisk() public {
        _publish(ValtideValidationRegistry.EvidenceState.CHALLENGED);

        vm.expectRevert(
            abi.encodeWithSelector(
                DemoCollateralVault.NewExposureNotAllowed.selector,
                ValtideValidationRegistry.EvidenceState.CHALLENGED,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
                true,
                true
            )
        );
        vm.prank(user);
        vault.requestNewExposure(100);
    }

    function testStalePathRequiresReview() public {
        _publishWithWindow(
            ValtideValidationRegistry.EvidenceState.SUPPORTED, block.timestamp - 60, block.timestamp + 60
        );
        vm.warp(block.timestamp + 61);

        vm.expectRevert(
            abi.encodeWithSelector(
                DemoCollateralVault.NewExposureNotAllowed.selector,
                ValtideValidationRegistry.EvidenceState.SUPPORTED,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
                true,
                false
            )
        );
        vm.prank(user);
        vault.requestNewExposure(100);
    }

    function testMonitorPathPermitsExposureAndReportsMonitor() public {
        vm.prank(owner);
        vault.configurePolicy(
            _policy(
                15 minutes,
                ValtideRiskGuard.PolicyAction.MONITOR,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
            )
        );
        _publish(ValtideValidationRegistry.EvidenceState.SUPPORTED);

        vm.prank(user);
        ValtideRiskGuard.PolicyAction action = vault.requestNewExposure(100);

        assertEq(uint8(action), uint8(ValtideRiskGuard.PolicyAction.MONITOR));
    }

    function testOnlyVaultOwnerCanConfigureVaultPolicy() public {
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, user));
        vm.prank(user);
        vault.configurePolicy(_defaultVaultPolicy());
    }

    function testEvidenceStateRemainsChallengedWhenVaultPolicyChanges() public {
        _publish(ValtideValidationRegistry.EvidenceState.CHALLENGED);

        (
            ValtideValidationRegistry.EvidenceState beforeState,
            ValtideRiskGuard.PolicyAction beforeAction,
            bool beforeExists,
            bool beforeFresh
        ) = riskGuard.evaluateFor(address(vault), ASSET_ID, REFERENCE_ID);
        assertEq(uint8(beforeState), uint8(ValtideValidationRegistry.EvidenceState.CHALLENGED));
        assertEq(uint8(beforeAction), uint8(ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK));
        assertTrue(beforeExists);
        assertTrue(beforeFresh);

        vm.expectRevert(
            abi.encodeWithSelector(
                DemoCollateralVault.NewExposureNotAllowed.selector,
                ValtideValidationRegistry.EvidenceState.CHALLENGED,
                ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
                true,
                true
            )
        );
        vm.prank(user);
        vault.requestNewExposure(100);

        vm.prank(owner);
        vault.configurePolicy(
            _policy(
                15 minutes,
                ValtideRiskGuard.PolicyAction.ALLOW,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
            )
        );

        (
            ValtideValidationRegistry.EvidenceState afterState,
            ValtideRiskGuard.PolicyAction afterAction,
            bool afterExists,
            bool afterFresh
        ) = riskGuard.evaluateFor(address(vault), ASSET_ID, REFERENCE_ID);
        assertEq(uint8(afterState), uint8(ValtideValidationRegistry.EvidenceState.CHALLENGED));
        assertEq(uint8(afterAction), uint8(ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW));
        assertTrue(afterExists);
        assertTrue(afterFresh);

        vm.expectRevert(
            abi.encodeWithSelector(
                DemoCollateralVault.NewExposureNotAllowed.selector,
                ValtideValidationRegistry.EvidenceState.CHALLENGED,
                ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
                true,
                true
            )
        );
        vm.prank(user);
        vault.requestNewExposure(100);
    }

    // ---------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------

    function _publish(ValtideValidationRegistry.EvidenceState evidenceState) internal {
        _publishWithWindow(evidenceState, block.timestamp - 60, block.timestamp + 900);
    }

    function _publishWithWindow(
        ValtideValidationRegistry.EvidenceState evidenceState,
        uint256 observedAt,
        uint256 validUntil
    ) internal {
        _publishInput(ASSET_ID, _attestation(evidenceState, observedAt, validUntil));
    }

    function _publishInput(bytes32 assetId, ValtideValidationRegistry.ValidationInput memory input) internal {
        vm.prank(publisher);
        registry.publishValidation(assetId, input);
    }

    function _attestation(ValtideValidationRegistry.EvidenceState evidenceState, uint256 observedAt, uint256 validUntil)
        internal
        pure
        returns (ValtideValidationRegistry.ValidationInput memory input)
    {
        input = ValtideValidationRegistry.ValidationInput({
            referenceId: REFERENCE_ID,
            referencePriceE8: 185_00000000,
            fairValueE8: 185_70000000,
            lowerBoundE8: 184_20000000,
            upperBoundE8: 187_20000000,
            referenceDeviationBps: 232,
            evidenceState: evidenceState,
            evidenceHash: keccak256(bytes("canonical-evidence")),
            modelVersion: keccak256(bytes("0.2.0")),
            observedAt: uint64(observedAt),
            validUntil: uint64(validUntil)
        });
    }

    function _defaultVaultPolicy() internal pure returns (ValtideRiskGuard.ValidationPolicy memory) {
        return _policy(
            15 minutes,
            ValtideRiskGuard.PolicyAction.ALLOW,
            ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
            ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
            ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
        );
    }

    function _policy(
        uint64 maxAge,
        ValtideRiskGuard.PolicyAction onSupported,
        ValtideRiskGuard.PolicyAction onInconclusive,
        ValtideRiskGuard.PolicyAction onChallenged,
        ValtideRiskGuard.PolicyAction onStale
    ) internal pure returns (ValtideRiskGuard.ValidationPolicy memory policy) {
        policy = ValtideRiskGuard.ValidationPolicy({
            maxAge: maxAge,
            onSupported: onSupported,
            onInconclusive: onInconclusive,
            onChallenged: onChallenged,
            onStale: onStale
        });
    }
}

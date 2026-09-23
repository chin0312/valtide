// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";

import {DemoCollateralVault} from "../src/DemoCollateralVault.sol";
import {ValtideRiskGuard} from "../src/ValtideRiskGuard.sol";
import {ValtideValidationRegistry} from "../src/ValtideValidationRegistry.sol";

contract DeployValtide is Script {
    bytes32 internal constant DEMO_ASSET_ID = keccak256(bytes("NVDAx"));
    bytes32 internal constant DEMO_REFERENCE_ID = keccak256(bytes("OKX_NVDA_USD_INDEX"));
    bytes32 internal constant DEMO_MODEL_VERSION = keccak256(bytes("0.2.0"));

    function run()
        external
        returns (ValtideValidationRegistry registry, ValtideRiskGuard riskGuard, DemoCollateralVault vault)
    {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address publisher = vm.envAddress("PUBLISHER_ADDRESS");
        address deployer = vm.addr(deployerPrivateKey);

        vm.startBroadcast(deployerPrivateKey);

        registry = new ValtideValidationRegistry(deployer);
        riskGuard = new ValtideRiskGuard(address(registry));
        vault = new DemoCollateralVault(deployer, address(riskGuard), DEMO_ASSET_ID, DEMO_REFERENCE_ID);

        registry.setPublisher(publisher, true);
        vault.configurePolicy(_defaultPolicy());

        vm.stopBroadcast();

        console2.log("ValtideValidationRegistry", address(registry));
        console2.log("ValtideRiskGuard", address(riskGuard));
        console2.log("DemoCollateralVault", address(vault));
        console2.log("DEMO_ASSET_ID");
        console2.logBytes32(DEMO_ASSET_ID);
        console2.log("DEMO_REFERENCE_ID");
        console2.logBytes32(DEMO_REFERENCE_ID);
        console2.log("DEMO_MODEL_VERSION");
        console2.logBytes32(DEMO_MODEL_VERSION);
    }

    function _defaultPolicy() internal pure returns (ValtideRiskGuard.ValidationPolicy memory policy) {
        policy = ValtideRiskGuard.ValidationPolicy({
            maxAge: 15 minutes,
            onSupported: ValtideRiskGuard.PolicyAction.ALLOW,
            onInconclusive: ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW,
            onChallenged: ValtideRiskGuard.PolicyAction.RESTRICT_NEW_RISK,
            onStale: ValtideRiskGuard.PolicyAction.REQUIRE_REVIEW
        });
    }
}

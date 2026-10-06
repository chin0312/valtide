// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";

import {DemoCollateralVault} from "../src/DemoCollateralVault.sol";
import {ValtideRiskGuard} from "../src/ValtideRiskGuard.sol";

/// @notice Adds the SPYx and AAPLx consumers to the already deployed shared
///         X Layer testnet control plane. This script never deploys a Registry
///         or RiskGuard.
contract ProvisionValtideAssets is Script {
    uint256 internal constant XLAYER_TESTNET_CHAIN_ID = 1952;
    address internal constant SHARED_REGISTRY = 0x1A53C85C66EA212693d36bF842574643C4d9B635;
    address internal constant SHARED_RISK_GUARD = 0x8e17a4eB93074ea74d05D9bc316d85AD3B540CE7;

    bytes32 internal constant SPY_ASSET_ID = keccak256(bytes("SPYx"));
    bytes32 internal constant SPY_REFERENCE_ID = keccak256(bytes("OKX_SPY_USD_INDEX"));
    bytes32 internal constant AAPL_ASSET_ID = keccak256(bytes("AAPLx"));
    bytes32 internal constant AAPL_REFERENCE_ID = keccak256(bytes("OKX_AAPL_USD_INDEX"));

    error UnsupportedChain(uint256 actualChainId);
    error SharedAddressMismatch(address suppliedRegistry, address suppliedRiskGuard);
    error MissingContractCode(address target);
    error RegistryLinkMismatch(address actualRegistry);

    function run() external returns (DemoCollateralVault spyVault, DemoCollateralVault aaplVault) {
        // Chain and shared-contract checks deliberately precede reading the
        // signer key or constructing any deployment transaction.
        (address registryAddress, address riskGuardAddress) = _preflight();

        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        vm.startBroadcast(deployerPrivateKey);

        spyVault = new DemoCollateralVault(deployer, riskGuardAddress, SPY_ASSET_ID, SPY_REFERENCE_ID);
        spyVault.configurePolicy(_defaultPolicy());

        aaplVault = new DemoCollateralVault(deployer, riskGuardAddress, AAPL_ASSET_ID, AAPL_REFERENCE_ID);
        aaplVault.configurePolicy(_defaultPolicy());

        vm.stopBroadcast();

        console2.log("Shared Registry", registryAddress);
        console2.log("Shared RiskGuard", riskGuardAddress);
        console2.log("Provisioning deployer", deployer);
        console2.log("SPYx DemoCollateralVault", address(spyVault));
        console2.log("SPYx assetId");
        console2.logBytes32(SPY_ASSET_ID);
        console2.log("SPYx referenceId");
        console2.logBytes32(SPY_REFERENCE_ID);
        console2.log("AAPLx DemoCollateralVault", address(aaplVault));
        console2.log("AAPLx assetId");
        console2.logBytes32(AAPL_ASSET_ID);
        console2.log("AAPLx referenceId");
        console2.logBytes32(AAPL_REFERENCE_ID);
    }

    function _preflight() internal view returns (address registryAddress, address riskGuardAddress) {
        if (block.chainid != XLAYER_TESTNET_CHAIN_ID) {
            revert UnsupportedChain(block.chainid);
        }

        registryAddress = vm.envAddress("REGISTRY_ADDRESS");
        riskGuardAddress = vm.envAddress("RISK_GUARD_ADDRESS");
        if (registryAddress != SHARED_REGISTRY || riskGuardAddress != SHARED_RISK_GUARD) {
            revert SharedAddressMismatch(registryAddress, riskGuardAddress);
        }
        if (registryAddress.code.length == 0) revert MissingContractCode(registryAddress);
        if (riskGuardAddress.code.length == 0) revert MissingContractCode(riskGuardAddress);

        address linkedRegistry = ValtideRiskGuard(riskGuardAddress).registry();
        if (linkedRegistry != registryAddress) revert RegistryLinkMismatch(linkedRegistry);
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

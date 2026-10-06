from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_provisioning_script_is_testnet_pinned_and_never_deploys_shared_contracts():
    source = (REPO_ROOT / "contracts" / "script" / "ProvisionValtideAssets.s.sol").read_text()
    run_start = source.index("function run()")
    preflight_call = source.index("_preflight();", run_start)
    read_signer = source.index('vm.envUint("DEPLOYER_PRIVATE_KEY")')
    start_broadcast = source.index("vm.startBroadcast(deployerPrivateKey)")
    preflight_start = source.index("function _preflight()")
    chain_guard = source.index("if (block.chainid != XLAYER_TESTNET_CHAIN_ID)", preflight_start)

    assert preflight_call < read_signer < start_broadcast
    assert preflight_start < chain_guard
    assert "0x1A53C85C66EA212693d36bF842574643C4d9B635" in source
    assert "0x8e17a4eB93074ea74d05D9bc316d85AD3B540CE7" in source
    assert source.count("new DemoCollateralVault(") == 2
    assert source.count(".configurePolicy(_defaultPolicy())") == 2
    assert "new ValtideValidationRegistry" not in source
    assert "new ValtideRiskGuard" not in source


def test_read_only_verifier_contains_no_transaction_or_signer_api():
    source = (REPO_ROOT / "scripts" / "verify_xlayer_asset.py").read_text()
    receipt_source = (
        REPO_ROOT / "scripts" / "capture_xlayer_provisioning_receipt.py"
    ).read_text()

    assert "_verify_deployment" in source
    assert "publisher_private_key" not in source
    assert "send_raw_transaction" not in source
    assert "sign_transaction" not in source
    assert "publish(" not in source
    assert "get_transaction_receipt" in receipt_source
    assert "send_raw_transaction" not in receipt_source
    assert "sign_transaction" not in receipt_source
    assert "startBroadcast" not in receipt_source

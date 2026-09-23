"""DexScreener pair-selection tests (pure logic, no network)."""

from valtide_api.adapters.dexscreener import _pick_best_pair, _to_quote


def _pair(symbol, price, liq, addr="p"):
    return {
        "baseToken": {"symbol": symbol},
        "priceUsd": price,
        "liquidity": {"usd": liq},
        "volume": {"h24": 1000},
        "pairAddress": addr,
        "chainId": "solana",
    }


def test_picks_deepest_liquidity_nvdax_pair():
    pairs = [
        _pair("NVDAx", "185.0", 10_000, "shallow"),
        _pair("NVDAx", "185.5", 500_000, "deep"),
        _pair("SOMETHING", "1.0", 9_000_000, "other"),
    ]
    best = _pick_best_pair(pairs, "NVDAx")
    assert best is not None
    assert best["pairAddress"] == "deep"


def test_ignores_non_nvdax_and_missing_price():
    pairs = [
        {"baseToken": {"symbol": "NVDAx"}, "liquidity": {"usd": 1_000_000}},  # no priceUsd
        _pair("USDC", "1.0", 5_000_000),
    ]
    assert _pick_best_pair(pairs, "NVDAx") is None


def test_symbol_match_is_case_insensitive():
    best = _pick_best_pair([_pair("nvdax", "185.0", 100)], "NVDAx")
    assert best is not None


def test_to_quote_reads_fields():
    q = _to_quote(_pair("NVDAx", "185.5", 500_000, "deep"))
    assert q.price == 185.5
    assert q.source == "dexscreener"
    assert q.liquidity_usd == 500_000
    assert q.chain == "solana"

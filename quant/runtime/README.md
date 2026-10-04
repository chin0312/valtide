# Runtime integration decision

Integrate the existing `valtide-quant-service-p1ac` package for **NVDAx P1a-C challenger estimation and calibrated uncertainty only**. The canonical production package remains at the repository root; `p1ac/code/` is a hash-verifiable handoff snapshot.

Backend engineers should integrate:

- the P1a sequential runtime and its causal update order;
- `p1ac/params/p1a_runtime.json` for NVDAx only;
- `p1ac/calibration/p1a_c_calibrator.json` for the same model/dataset binding;
- `SUPPORT / WATCH / REVIEW` as product language only when the backend owns the policy and clearly states that `REVIEW` means scrutiny, not automatic replacement;
- raw xStock as the ordinary primary observable reference.

Do **not** integrate:

- P1a as a universal replacement point price;
- artifacts from other assets—the handoff contains no approved runtime parameters for them;
- the fitted lag-vs-dislocation gate;
- P1m or P1m-C;
- Raw-xStock-C as the production interval layer;
- current underlying values or retrospective diagnostic features as live inputs;
- fixed cross-asset challenger thresholds without fresh untouched validation.

The frozen runtime is bound to NVDAx dataset SHA-256 `722929383e6ca1aa28382e828879efeccb60faabdf2bd5e05f14a721f7fc740d` and model version `0.2.0`. Run `python run_deterministic_tests.py` from `runtime/p1ac/` before integration. Teams with pytest installed may also run `python -m pytest -q tests`.

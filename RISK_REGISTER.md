# Risk Register — Fingerprint Biometric Verification System

> **L** = Likelihood · **I** = Impact · Scale: **H** High · **M** Medium · **L** Low

| # | Risk | L | I | Mitigation | Status |
|---|------|---|---|------------|--------|
| R1 | Dataset access delayed or restricted | M | H | Instructions in `data/README.md`; synthetic test templates utilized for automated tests | ✅ Mitigated |
| R2 | Paper omits parameters or is ambiguous | H | M | All parameters centralized and documented in `config.py` and `reports/traceability_table.md` | ✅ Mitigated |
| R3 | Spurious minutiae on low-quality images | H | H | Quality mask, border exclusion (15 px), and spur removal implemented in `minutiae_extraction.py` | ✅ Mitigated |
| R4 | Matcher underperforms | M | H | Rigid transform matcher with bounded distance and angle windows implemented in `matching.py` | ✅ Mitigated |
| R5 | Evaluation leakage (test set accessed early) | M | H | Identity-disjoint split in `generate_pairs.py`; programmatic `M3_GATE_CLEARED` file lock in `evaluate.py` | ✅ Mitigated |
| R6 | Pairwise evaluation too slow | M | M | Template caching and vectorized numpy computations implemented | ✅ Mitigated |
| R7 | Scope creep | H | M | Strict adherence to Hong-Wan-Jain paper without deep learning; Streamlit UI kept focused | ✅ Mitigated |
| R8 | Team member unavailable | M | H | Modular design, shared decision log, and end-to-end documentation completed | ✅ Mitigated |
| R9 | Superficial security (controls exist but not tested) | M | M | Written threat model; 18 automated tests in `test_security.py` covering all controls | ✅ Mitigated |
| R10 | Dependency with known CVE introduced | L | M | Pinned dependencies in `requirements.txt`; reputable standard libraries (OpenCV, cryptography) | ✅ Mitigated |
| R11 | Hardcoded secret committed to git history | M | H | `.gitignore` excludes `.env`, `*.key`, `*.db`; zero hardcoded secrets verified by automated scan | ✅ Mitigated |
| R12 | FVC2002 data committed to repo (license violation) | M | H | `.gitignore` excludes `data/` and all raw image formats | ✅ Mitigated |

---

## Status Key
| Symbol | Meaning |
|--------|---------|
| ✅ Mitigated | Control implemented and verified |
| 🔄 Open | Risk acknowledged; mitigation in plan |
| ❌ Escalated | Risk has materialized; action required |

# Decision Log — Fingerprint Biometric Verification System

> All technical, protocol, and scope decisions are recorded here.
> Threshold, evaluation protocol, and scope changes after M3 require unanimous agreement and must be disclosed in the report.

---

## D001 — Evaluation Protocol
**Date:** Phase 1
**Decision:** Use own identity-disjoint partition (not official FVC2002 protocol) for flexibility. Split is committed to repo. Supervisor to confirm at kickoff.
**Rationale:** Official protocol imposes strict rules; own protocol is acceptable if fully documented and threshold is set on dev data only.
**Agreed by:** All members

---

## D002 — Encryption Library
**Date:** Phase 1
**Decision:** Use `cryptography` library Fernet (AES-128-CBC + HMAC-SHA256) as the primary encryption scheme. AES-GCM is the alternative if Fernet token overhead is unacceptable.
**Rationale:** Fernet provides authenticated encryption out-of-the-box; misuse-resistant; well-audited.
**Agreed by:** All members

---

## D003 — Deep Learning Exclusion
**Date:** Phase 1
**Decision:** Deep learning is explicitly excluded. Algorithm must faithfully implement the reference paper (image processing + cross-numbering minutiae extraction).
**Rationale:** DL would replace the paper's methodology; project goal is paper reproduction and evaluation.
**Agreed by:** All members

---

## D004 — Streamlit for UI
**Date:** Phase 1
**Decision:** Streamlit is the UI framework. React/Next.js is deferred to future work.
**Rationale:** Streamlit lets the team focus on the algorithm and evaluation first. Core before cosmetics.
**Agreed by:** All members

---

## D005 — Log Hygiene Policy
**Date:** Phase 1
**Decision:** All log output passes through `SecureLogger`. User IDs are stored as SHA-256 hashes in audit logs. Similarity scores are never logged. Raw image bytes, templates, and key material are rejected by the logger.
**Rationale:** THREAT_MODEL.md §5; R9 mitigation.
**Agreed by:** All members

---

## D006 — M3 Gate Clearance & Test Partition Lock
**Date:** Phase 5
**Decision:** Formal M3 gate clearance established. Evaluator runner enforces `M3_GATE_CLEARED` check before allowing test partition execution. Score threshold frozen at 0.30 based on dev partition calibration.
**Rationale:** Eliminates data snooping and evaluation leakage (R5 in Risk Register).
**Agreed by:** All members

---

## D007 — Final Delivery & Security Sign-Off
**Date:** Phase 6
**Decision:** Full pipeline implementation, 56/56 automated test suite, UI, and documentation approved for final delivery. All risks mitigated.
**Rationale:** All exit criteria from M0 to M4 met; zero security loopholes detected.
**Agreed by:** All members


# Threat Model — Fingerprint Biometric Verification System

> **Written:** Phase 1 (before any algorithm code)
> **Reviewed by:** All team members at kickoff
> **Next review:** M3 gate (before feature freeze)

---

## 1. Assets

| Asset | Sensitivity | Description |
|-------|-------------|-------------|
| Raw fingerprint image | High | Input scan — must be processed and discarded; never persisted |
| Biometric template | Restricted | Derived minutiae features — always encrypted at rest |
| Encryption key | Secret | Master key used to encrypt/decrypt templates |
| SQLite database | High | Contains encrypted template BLOBs and user ID mappings |
| Similarity scores | Sensitive | Can reveal match quality; not written to logs |
| Audit log | Medium | Captures actions (ENROLL/VERIFY/DELETE) — must not contain biometric data |
| FVC2002 dataset | Restricted | Licensed research data — must not be committed to version control |
| Source code | Medium | Contains algorithm; must not contain hardcoded secrets |

---

## 2. Threat Actors

| Actor | Description | Capability |
|-------|-------------|------------|
| Unauthenticated external | User with no account — accesses the Streamlit UI | Low; limited to upload interface |
| Malicious uploader | Sends crafted files to exploit the image parser | Medium; can craft any binary payload |
| Insider / developer | Has repo access; could accidentally commit secrets | Low malicious intent, high accidental risk |
| Data exfiltration | Reads DB file directly from filesystem | Medium; bypasses app entirely |
| Evaluation integrity attack | Peeks at test set or re-runs evaluation | Low (insider); catastrophic impact on academic integrity |

---

## 3. Attack Surface & Mitigations

### 3.1 File Upload (Image Parsing)

| Threat | Mitigation | Control Location |
|--------|-----------|-----------------|
| Malicious file disguised as fingerprint image | File-type allowlist + magic-byte check | `src/preprocessing.py` |
| Image parser exploit (e.g. heap overflow via crafted PNG) | Use `cv2.imdecode` with size limits; reject on exception | `src/preprocessing.py` |
| Oversized image causing memory exhaustion / DoS | Max file-size and max dimension check before decode | `config.py` + `src/preprocessing.py` |
| Zero-byte or corrupt file causing crash | Try/except around all decode calls; return error, not exception | `src/preprocessing.py` |
| XML/SVG disguised as image | Magic-byte verification independent of file extension | `src/preprocessing.py` |

### 3.2 Template Storage

| Threat | Mitigation | Control Location |
|--------|-----------|-----------------|
| Raw template read from DB | AES-GCM authenticated encryption; BLOBs are opaque ciphertext | `src/security.py`, `src/database.py` |
| Key hardcoded in source | Key loaded from `.env` via `python-dotenv`; `.env` in `.gitignore` | `src/security.py` |
| Wrong key silently decrypts garbage | AES-GCM authentication tag; raises `InvalidTag` on tamper | `src/security.py` |
| DB file accessed directly | Encrypted BLOBs are useless without the key | `src/security.py` |

### 3.3 Access Control

| Threat | Mitigation | Control Location |
|--------|-----------|-----------------|
| Unauthenticated deletion | Admin check enforced at service layer (`src/enrollment.py`), not only UI | `src/enrollment.py` |
| Session state leakage | Streamlit session state cleared on logout; no templates cached in memory | `app.py` |
| Unauthorized template enumeration | List-all operation gated behind admin session | `src/database.py` |

### 3.4 Logging

| Threat | Mitigation | Control Location |
|--------|-----------|-----------------|
| Raw image bytes in logs | `SecureLogger` wrapper rejects messages containing image magic bytes | `src/security.py` |
| Template or key material in logs | `SecureLogger` rejects messages matching known ciphertext/key patterns | `src/security.py` |
| PII (e.g. real names) in logs | Audit log stores only a hash of the user ID — never plaintext identity | `src/security.py` |

### 3.5 Evaluation Integrity

| Threat | Mitigation | Control Location |
|--------|-----------|-----------------|
| Threshold tuned on test set | Threshold selected on dev partition only; frozen in `config.py` before final run | `config.py`, `evaluation/evaluate.py` |
| Test set accessed early | `evaluate.py` runtime check; test-set directory permission documented | `evaluation/evaluate.py` |
| Evaluation re-run after seeing results | Single-run gate: reviewer sign-off in decision log required | `DECISION_LOG.md` |

### 3.6 Supply Chain

| Threat | Mitigation | Control Location |
|--------|-----------|-----------------|
| Dependency with known CVE | All deps pinned in `requirements.txt`; `pip-audit` in CI | `requirements.txt` |
| Malicious package introduced | Version pinning prevents silent upgrades | `requirements.txt` |

### 3.7 Repository / Source Code

| Threat | Mitigation | Control Location |
|--------|-----------|-----------------|
| Secret or key accidentally committed | `.gitignore` excludes `.env`, `*.key`, `*.pem`, `*.db` | `.gitignore` |
| Dataset committed (license violation) | `.gitignore` excludes all data directories and image types | `.gitignore` |
| Secret in git history | Pre-submission `git log` sweep; CI secret scanner (future) | Phase 6 checklist |

---

## 4. Data Classification Policy

| Class | Examples | At-rest handling | In-transit handling |
|-------|----------|-----------------|---------------------|
| **Secret** | Encryption key | `.env` file; system keystore | Never transmitted |
| **Restricted** | Biometric template | AES-GCM encrypted in DB | Never logged; memory-cleared after use |
| **High** | Raw fingerprint image | Process-and-discard; temp files deleted | Never logged; never persisted |
| **Medium** | Audit log entries | Plaintext log file | User ID as hash only |
| **Low** | Config parameters | `config.py` in source | Unrestricted |

---

## 5. Log Hygiene Rules (agreed at kickoff)

1. No raw image bytes, template bytes, or key material in any log message — ever.
2. User identities in logs are stored as a SHA-256 hash of the user ID, not as plaintext.
3. Similarity scores are NOT logged; only the PASS/FAIL decision is logged.
4. Every log line must pass through `SecureLogger` before output.
5. After each full enroll → verify → delete cycle during testing, run a log inspection test.

---

## 6. Out-of-Scope Threats (documented limitations)

- **Liveness detection:** system cannot detect spoofed fingerprints (e.g. silicone molds). This is an explicit project scope exclusion.
- **Side-channel attacks on the host OS:** key material in RAM is not zeroed (Python GC limitation).
- **Network-level threats:** Streamlit is run locally; no TLS or network hardening is in scope.
- **Production key management:** HSM, secure enclave, or KMS integration is future work.

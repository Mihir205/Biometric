# Fingerprint Biometric Verification System

> **Status:** Implementation complete | **Phase:** See [PHASE_PLAN.md](./PHASE_PLAN.md)
> **Paper:** *Fingerprint Image Enhancement and Extraction of Minutiae and Orientation*
> **Dataset:** FVC2002 (see [data/README.md](./data/README.md) for access instructions)

---

## Quick Start

```bash
# 1. Create environment and install pinned dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -r requirements.txt

# 2. Set up the encryption key (NEVER commit this to git)
#    Create a .env file in the project root:
echo BIOMETRIC_MASTER_SECRET=<your-64-hex-char-secret> > .env
echo BIOMETRIC_ADMIN_SECRET=<your-admin-password>     >> .env

# 3. Place the FVC2002 dataset under data/ (see data/README.md)

# 4. Run tests
pytest --cov=src tests/

# 5. Launch the application
python -m streamlit run app.py
# Open your browser to http://localhost:8501
```

---

## Web Application User Guide

The Streamlit web interface (`app.py`) provides an interactive workflow for enrolling fingerprints, verifying identity, and administrative template management.

### Getting the Benchmark Dataset (FVC2002 DB1_B)

For real evaluation and presentation demos, download the official **FVC2002 DB1_B** benchmark dataset (80 genuine optical impressions, 10 fingers × 8 impressions each):

```bash
python data/download_dataset.py
```
This automatically downloads and unpacks the 80 images into `data/DB1_B/`:
- `101_1.tif` to `101_8.tif`: Finger 101 impressions
- `102_1.tif` to `102_8.tif`: Finger 102 impressions
- ... up to `110_8.tif`

*(Alternatively, you can run `python data/create_samples.py` if you prefer 3 quick synthetic sample images in `data/samples/`).*

---

### Step-by-Step UI Guide

#### 1. 📥 Tab 1: Enroll a Fingerprint
1. Switch to the **📥 Enroll** tab.
2. Enter a **User ID** (e.g., `user_101`).
3. Click **Browse files** and select a real benchmark impression (e.g., `data/DB1_B/101_1.tif`).
4. Click **Enroll**.
   - **Under the hood:** The system verifies file magic bytes, normalizes the ridge pattern, extracts minutiae, encrypts the feature template using authenticated AES-128-CBC + HMAC-SHA256 (Fernet), and stores it in SQLite (`biometric.db`). The raw uploaded image is immediately discarded and never saved.
   - Successful enrollment displays: `✅ User user_101 enrolled successfully.`
   - *Note: Re-enrolling an existing user ID is prevented unless "Allow re-enrollment" is checked with an active Admin session.*

#### 2. 🔍 Tab 2: Verify a Fingerprint (1:1 Matching)
1. Switch to the **🔍 Verify** tab.
2. Enter the **User ID to verify against** (e.g., `user_101`).
3. **Demonstrate Genuine Verification (Accepted):**
   - Upload another impression of the **same finger**: `data/DB1_B/101_2.tif`.
   - Click **Verify** → Output: `✅ ACCEPTED — Fingerprints match.`
4. **Demonstrate Impostor Rejection (Rejected):**
   - Upload an impression from a **different finger**: `data/DB1_B/102_1.tif`.
   - Click **Verify** → Output: `❌ REJECTED — Fingerprints do not match.`
   - **Anti-Hill-Climbing Defense:** Numeric similarity scores are intentionally hidden from the UI to protect against gradient-based biometric synthesis and hill-climbing attacks.

#### 3. 🛠 Tab 3: Admin & Secure Template Deletion
1. Open the left sidebar and enter the **Admin password** (configured via `BIOMETRIC_ADMIN_SECRET` in `.env`, e.g., `admin123`).
2. Click **Login** to activate the admin session.
3. Switch to the **🛠 Admin** tab:
   - View the list of all currently enrolled user IDs.
   - Click **Delete** next to any user ID to transactionally scrub their encrypted template from the database with zero residual artifacts.
4. Click **Logout** in the sidebar at any time to clear the session state.

---

## Project Structure

```
fingerprint-biometric-system/
├── app.py                     # Streamlit UI — enroll / verify / admin delete
├── config.py                  # Single source of truth for all parameters
├── requirements.txt           # Pinned dependencies
├── PHASE_PLAN.md              # 6-phase plan with progress tracking
├── THREAT_MODEL.md            # Written threat model (Phase 1)
├── DECISION_LOG.md            # Governance decision log
├── RISK_REGISTER.md           # R1–R12 risk register
├── .env                       # ⚠️ NOT in git — master secret and admin password
├── src/
│   ├── security.py            # SecureLogger, key management, encryption, audit log
│   ├── preprocessing.py       # Input validation, normalisation
│   ├── orientation.py         # Gradient-based orientation field estimation
│   ├── enhancement.py         # Gabor-filter ridge enhancement
│   ├── segmentation.py        # Foreground mask, skeletonisation
│   ├── minutiae_extraction.py # Cross-number extraction, spurious removal
│   ├── template.py            # Template data model, JSON serialisation
│   ├── matching.py            # Minutiae matcher with alignment scoring
│   ├── database.py            # Encrypted SQLite template store
│   ├── enrollment.py          # Enrollment service (full pipeline)
│   └── verification.py        # Verification service (full pipeline)
├── evaluation/
│   ├── generate_pairs.py      # Identity-disjoint partition + pair generation
│   ├── evaluate.py            # Evaluation runner (M3 gate on test partition)
│   └── metrics.py             # FAR, FRR, EER, bootstrap CIs
├── tests/
│   ├── test_preprocessing.py  # Input validation + adversarial tests
│   ├── test_minutiae.py       # Minutiae extraction on synthetic skeletons
│   ├── test_matching.py       # Matcher on synthetic templates
│   ├── test_database.py       # Encryption, deletion, residual data
│   └── test_security.py       # All security controls (per THREAT_MODEL.md)
├── data/
│   └── README.md              # Dataset access and license instructions
└── reports/
    └── results/               # Timestamped evaluation result JSON files
```

---

## Security Overview

| Layer | Control |
|-------|---------|
| Input | File-type allowlist + magic-byte check + size/dimension limits |
| Template | AES-128-CBC + HMAC-SHA256 (Fernet) authenticated encryption |
| Key | PBKDF2-HMAC-SHA256 from `.env` — never hardcoded or in DB |
| Access | Admin operations enforced at service layer |
| Logging | `SecureLogger` rejects images, templates, keys; audit log hashes user IDs |
| Deletion | Transactional; no residual data |
| Evaluation | M3 gate lock on test partition; single run; frozen threshold |
| Supply chain | Pinned deps; `pip-audit` for CVE checking |

See [THREAT_MODEL.md](./THREAT_MODEL.md) for the full threat model.

---

## Limitations

- No **liveness detection** or **spoof resistance** — a silicone fingerprint mold would not be detected.
- No **live sensor** — images come from the FVC2002 research dataset.
- The security measures make the system **security-conscious** but do not guarantee the absence of vulnerabilities. This prototype is **not suitable for production deployment** without further hardening (HSM, secure enclave, TLS, rate limiting, etc.).
- Deep learning is deliberately excluded to maintain faithful paper reproduction.

---

## Citation

If you use FVC2002 data, cite:

> D. Maio, D. Maltoni, R. Cappelli, J.L. Wayman, A.K. Jain, "FVC2002: Second Fingerprint Verification Competition", *Proc. 16th IAPR Int. Conf. on Pattern Recognition*, Québec City, Canada, August 2002.

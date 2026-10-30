# Paper-to-Code Traceability Table

> Every algorithm stage is mapped to its paper section, implementation file, and `config.py` key.
> Deviations from the paper are documented with rationale.

| Paper § | Stage | Implementation | Config keys | Deviations |
|---------|-------|----------------|-------------|------------|
| §3.1 | Image normalisation | `src/preprocessing.py :: normalise()` | `NORMALISE_MEAN`, `NORMALISE_VAR` | Clipped to ±3σ then rescaled to [0,1] for numerical stability |
| §3.2 | Orientation estimation | `src/orientation.py :: estimate()` | `ORIENTATION_BLOCK_SIZE`, `ORIENTATION_SMOOTH_SIGMA` | Gaussian smoothing applied to double-angle vector field (standard practice) |
| §3.3 | Gabor enhancement | `src/enhancement.py :: enhance()` | `GABOR_KERNEL_SIZE`, `GABOR_SIGMA_X`, `GABOR_SIGMA_Y`, `GABOR_LAMBDA`, `GABOR_GAMMA`, `NUM_GABOR_ORIENTATIONS` | None — faithful reproduction |
| §3.4 | Segmentation | `src/segmentation.py :: segment()` | `SEGMENT_BLOCK_SIZE`, `SEGMENT_VAR_THRESHOLD` | Morphological closing added post-mask (not in paper) to reduce noise |
| §3.5 | Skeletonisation | `src/segmentation.py :: skeletonise()` | — | Uses scikit-image `skeletonize` (Zhang-Suen algorithm); paper unspecified algorithm |
| §4.1 | Minutiae extraction (crossing number) | `src/minutiae_extraction.py :: extract()` | `MINUTIAE_BORDER_MARGIN` | Border exclusion margin added (not in paper) — standard practice |
| §4.2 | Spurious minutiae removal | `src/minutiae_extraction.py :: remove_spurious()` | `MINUTIAE_MIN_RIDGE_LEN` | Short-ridge pruning via connected component labelling; paper describes method conceptually |
| §5 | Minutiae matching | `src/matching.py :: match()` | `MATCH_DISTANCE_THRESHOLD`, `MATCH_ANGLE_THRESHOLD_DEG`, `MATCH_SCORE_THRESHOLD` | Exhaustive anchor-pair alignment; Jaccard-like score; paper describes principle not exact algorithm |

---

## Evaluation Parameters

| Parameter | Value | Source | Config key |
|-----------|-------|---------|------------|
| Random seed | 42 | Project decision | `EVAL_RANDOM_SEED` |
| Dev fraction | 70% | Project decision | `EVAL_DEV_FRACTION` |
| Impostor pairs per finger | 5 | Project decision | `EVAL_IMPOSTOR_PAIRS_PER_FINGER` |
| Bootstrap iterations | 1000 | Standard practice | `EVAL_BOOTSTRAP_ITERATIONS` |
| Score threshold | 0.30 | Tuned on dev data | `MATCH_SCORE_THRESHOLD` |

---

## Security Parameters

| Parameter | Value | Standard/Rationale | Config key |
|-----------|-------|-------------------|------------|
| PBKDF2 iterations | 480,000 | OWASP 2024 recommendation | `KEY_DERIVATION_ITERATIONS` |
| Key length | 256 bit | AES-256 equivalent | `KEY_LENGTH_BYTES` |
| Encryption scheme | Fernet (AES-128-CBC + HMAC-SHA256) | Authenticated; misuse-resistant | — |

"""
config.py — Single source of truth for all tuneable parameters.

Rules:
- Every parameter here must be referenced in the traceability table (reports/traceability_table.md).
- Parameters derived from the paper carry a PAPER_REF comment.
- Parameters chosen empirically carry a DEV_TUNED comment (tuned on dev data only).
- NEVER hard-code any of these values elsewhere in the codebase.
"""

# ─── Input validation ─────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}

# Magic bytes for each allowed type: (offset, bytes)
MAGIC_BYTES = {
    ".png":  (0, b"\x89PNG\r\n\x1a\n"),
    ".bmp":  (0, b"BM"),
    ".tif":  (0, b"II"),   # little-endian TIFF
    ".tiff": (0, b"II"),
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB hard limit
MIN_IMAGE_DIM = 50                       # pixels — reject tiny/degenerate images
MAX_IMAGE_DIM = 1500                     # pixels — reject unreasonably large images

# ─── Preprocessing ────────────────────────────────────────────────────────────
NORMALISE_MEAN = 0.0      # PAPER_REF: §3.1 — zero-mean normalisation
NORMALISE_VAR  = 1.0      # PAPER_REF: §3.1 — unit-variance normalisation

# ─── Orientation estimation ───────────────────────────────────────────────────
ORIENTATION_BLOCK_SIZE = 16    # PAPER_REF: §3.2 — block size (pixels) for gradient averaging
ORIENTATION_SMOOTH_SIGMA = 7.0 # DEV_TUNED — Gaussian smoothing applied to orientation field

# ─── Gabor enhancement ────────────────────────────────────────────────────────
GABOR_KERNEL_SIZE = (16, 16)   # PAPER_REF: §3.3 — Gabor filter kernel dimensions
GABOR_SIGMA_X = 4.0            # PAPER_REF: §3.3
GABOR_SIGMA_Y = 4.0            # PAPER_REF: §3.3
GABOR_LAMBDA = 9.0             # PAPER_REF: §3.3 — wavelength (≈ ridge spacing in pixels)
GABOR_GAMMA = 1.0              # PAPER_REF: §3.3 — spatial aspect ratio
NUM_GABOR_ORIENTATIONS = 8     # PAPER_REF: §3.3 — number of filter orientations

# ─── Segmentation ─────────────────────────────────────────────────────────────
SEGMENT_BLOCK_SIZE = 16        # PAPER_REF: §3.4 — block size for variance-based segmentation
SEGMENT_VAR_THRESHOLD = 100.0  # DEV_TUNED — variance below this → background

# ─── Minutiae extraction ──────────────────────────────────────────────────────
MINUTIAE_BORDER_MARGIN = 15    # DEV_TUNED — pixels to exclude from image border
MINUTIAE_MIN_RIDGE_LEN = 10    # DEV_TUNED — minimum ridge branch length (spur removal)

# ─── Template ─────────────────────────────────────────────────────────────────
TEMPLATE_VERSION = "1.0"       # Bump when template schema changes (breaks compatibility)
MAX_MINUTIAE_PER_TEMPLATE = 150

# ─── Matching ─────────────────────────────────────────────────────────────────
MATCH_DISTANCE_THRESHOLD = 15  # DEV_TUNED — pixels — max distance to consider minutiae paired
MATCH_ANGLE_THRESHOLD_DEG = 20 # DEV_TUNED — degrees — max angle difference for a pair
MATCH_SCORE_THRESHOLD = 0.30   # DEV_TUNED — minimum score to accept a match
                                # NOTE: frozen after M3; MUST NOT be changed after final test run

# ─── Evaluation ───────────────────────────────────────────────────────────────
EVAL_RANDOM_SEED = 42
EVAL_IMPOSTOR_PAIRS_PER_FINGER = 5   # seeded random sample
EVAL_DEV_FRACTION = 0.7              # proportion of identities for dev partition
EVAL_BOOTSTRAP_ITERATIONS = 1000
EVAL_MAX_IMPOSTOR_PAIRS = 10_000     # cap to keep evaluation tractable

# ─── Security ─────────────────────────────────────────────────────────────────
KEY_DERIVATION_ITERATIONS = 480_000  # PBKDF2-HMAC-SHA256; OWASP 2024 recommendation
KEY_LENGTH_BYTES = 32                # 256-bit key for AES-GCM
FERNET_TOKEN_TTL = None              # No TTL on stored templates (they are long-lived)

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
# Patterns that must NEVER appear in a log line (enforced by SecureLogger)
LOG_SENSITIVE_PATTERNS = [
    b"\x89PNG",           # PNG magic bytes
    b"BM",                # BMP magic bytes
    b"II*",               # TIFF magic bytes
    b"gAAAAA",            # Fernet token prefix (base64)
]

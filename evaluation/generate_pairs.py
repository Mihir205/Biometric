"""
evaluation/generate_pairs.py — Generate genuine and impostor pair lists.

Evaluation protocol:
  - Partition identities into dev (70%) and test (30%) — IDENTITY DISJOINT.
  - All impressions of a finger stay in the same partition.
  - Genuine pairs: all unordered impression pairs per finger (C(n,2) per finger).
  - Impostor pairs: a seeded random sample across different fingers.
  - The split file is committed to the repo for reproducibility.
  - Test-set pairs are generated here but MUST NOT be evaluated until Phase 5.

Security: This script must NOT load or expose template data.
"""

from __future__ import annotations

import json
import os
import pathlib
import random

import config

EVAL_DIR = pathlib.Path(__file__).parent
DATA_DIR = pathlib.Path(__file__).parent.parent / "data"
PAIRS_DIR = EVAL_DIR / "pairs"
PAIRS_DIR.mkdir(exist_ok=True)

SPLIT_FILE = PAIRS_DIR / "split.json"
DEV_GENUINE_FILE = PAIRS_DIR / "dev_genuine.json"
DEV_IMPOSTOR_FILE = PAIRS_DIR / "dev_impostor.json"
TEST_GENUINE_FILE = PAIRS_DIR / "test_genuine.json"
TEST_IMPOSTOR_FILE = PAIRS_DIR / "test_impostor.json"


def discover_dataset(data_dir: pathlib.Path) -> dict[str, list[str]]:
    """
    Discover fingerprint images grouped by finger identity.

    Expects files named: <finger_id>_<impression>.ext
    e.g. 101_1.tif, 101_2.tif, 102_1.tif ...

    Returns:
        Dict mapping finger_id (str) → list of absolute file paths.
    """
    allowed = config.ALLOWED_EXTENSIONS
    fingers: dict[str, list[str]] = {}

    for f in sorted(data_dir.rglob("*")):
        if f.suffix.lower() not in allowed:
            continue
        # FVC2002 naming convention: NNN_M.ext
        parts = f.stem.split("_")
        if len(parts) < 2:
            continue
        finger_id = parts[0]
        fingers.setdefault(finger_id, []).append(str(f.resolve()))

    return fingers


def split_identities(
    fingers: dict[str, list[str]],
    dev_fraction: float = config.EVAL_DEV_FRACTION,
    seed: int = config.EVAL_RANDOM_SEED,
) -> tuple[list[str], list[str]]:
    """Split finger IDs into dev and test partitions (identity-disjoint)."""
    ids = sorted(fingers.keys())
    rng = random.Random(seed)
    rng.shuffle(ids)
    split_idx = int(len(ids) * dev_fraction)
    return ids[:split_idx], ids[split_idx:]


def generate_genuine_pairs(
    fingers: dict[str, list[str]],
    ids: list[str],
) -> list[tuple[str, str]]:
    """All unordered impression pairs for each finger in ids."""
    pairs = []
    for fid in ids:
        impressions = fingers.get(fid, [])
        for i in range(len(impressions)):
            for j in range(i + 1, len(impressions)):
                pairs.append((impressions[i], impressions[j]))
    return pairs


def generate_impostor_pairs(
    fingers: dict[str, list[str]],
    ids: list[str],
    n: int = config.EVAL_IMPOSTOR_PAIRS_PER_FINGER,
    max_pairs: int = config.EVAL_MAX_IMPOSTOR_PAIRS,
    seed: int = config.EVAL_RANDOM_SEED,
) -> list[tuple[str, str]]:
    """Seeded random sample of cross-finger pairs from ids."""
    rng = random.Random(seed + 1)  # different seed from split
    id_list = sorted(ids)
    pairs = []
    for i, fid1 in enumerate(id_list):
        pool = [fid for j, fid in enumerate(id_list) if j != i]
        sampled = rng.sample(pool, min(n, len(pool)))
        for fid2 in sampled:
            img1 = rng.choice(fingers[fid1])
            img2 = rng.choice(fingers[fid2])
            pairs.append((img1, img2))
    rng.shuffle(pairs)
    return pairs[:max_pairs]


def main() -> None:
    print("Discovering dataset...")
    fingers = discover_dataset(DATA_DIR)
    if not fingers:
        print(f"No images found in {DATA_DIR}. Place the FVC2002 dataset there first.")
        return

    print(f"Found {len(fingers)} fingers, {sum(len(v) for v in fingers.values())} impressions.")

    dev_ids, test_ids = split_identities(fingers)
    print(f"Dev: {len(dev_ids)} fingers | Test: {len(test_ids)} fingers")

    # Save split
    split = {"dev": dev_ids, "test": test_ids, "seed": config.EVAL_RANDOM_SEED}
    SPLIT_FILE.write_text(json.dumps(split, indent=2))
    print(f"Split saved to {SPLIT_FILE}")

    # Dev pairs
    dev_genuine = generate_genuine_pairs(fingers, dev_ids)
    dev_impostor = generate_impostor_pairs(fingers, dev_ids)
    DEV_GENUINE_FILE.write_text(json.dumps(dev_genuine))
    DEV_IMPOSTOR_FILE.write_text(json.dumps(dev_impostor))
    print(f"Dev  genuine={len(dev_genuine)} impostor={len(dev_impostor)}")

    # Test pairs (generated now but evaluated only in Phase 5)
    test_genuine = generate_genuine_pairs(fingers, test_ids)
    test_impostor = generate_impostor_pairs(fingers, test_ids)
    TEST_GENUINE_FILE.write_text(json.dumps(test_genuine))
    TEST_IMPOSTOR_FILE.write_text(json.dumps(test_impostor))
    print(f"Test genuine={len(test_genuine)} impostor={len(test_impostor)}")
    print("IMPORTANT: Do NOT run evaluate.py --partition test until M3 gate is cleared.")


if __name__ == "__main__":
    main()

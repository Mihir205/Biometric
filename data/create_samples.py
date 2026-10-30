"""
data/create_samples.py — Utility to generate synthetic fingerprint test images.

Creates:
  - data/sample_alice_1.png (Alice's enrollment print)
  - data/sample_alice_2.png (Alice's verification probe print - genuine match)
  - data/sample_bob_1.png   (Bob's print - impostor print)
"""

import numpy as np
import cv2
from pathlib import Path

OUT_DIR = Path(__file__).parent / "samples"
OUT_DIR.mkdir(exist_ok=True)

def generate_fingerprint_pattern(center_offset=(0, 0), frequency=0.15, angle_bias=0.0, seed=42):
    rng = np.random.default_rng(seed)
    h, w = 300, 300
    y, x = np.mgrid[:h, :w]
    cx, cy = w // 2 + center_offset[0], h // 2 + center_offset[1]
    
    # Distance from core
    r = np.sqrt((x - cx)**2 + (y - cy)**2)
    theta = np.arctan2(y - cy, x - cx) + angle_bias
    
    # Generate concentric ridge-valley pattern with spiral modulation
    ridges = np.sin(r * frequency + 3 * np.cos(theta))
    
    # Add circular envelope / foreground mask
    mask = (r < 110).astype(np.float32)
    mask = cv2.GaussianBlur(mask, (21, 21), 0)
    
    # Combine ridges with mask and background
    img = (ridges * 0.5 + 0.5) * mask + (1.0 - mask) * 0.9
    img = np.clip(img * 255.0, 0, 255).astype(np.uint8)
    
    # Add slight realistic texture noise
    noise = rng.normal(0, 8, img.shape).astype(np.float32)
    noisy_img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return noisy_img

if __name__ == "__main__":
    # Alice: Enrollment (impression 1)
    alice_1 = generate_fingerprint_pattern(center_offset=(0, 0), frequency=0.14, angle_bias=0.0, seed=101)
    cv2.imwrite(str(OUT_DIR / "sample_alice_1.png"), alice_1)

    # Alice: Probe (impression 2 - genuine match with slight shift and noise)
    alice_2 = generate_fingerprint_pattern(center_offset=(3, -2), frequency=0.14, angle_bias=0.03, seed=102)
    cv2.imwrite(str(OUT_DIR / "sample_alice_2.png"), alice_2)

    # Bob: Impostor (different frequency and structure)
    bob_1 = generate_fingerprint_pattern(center_offset=(15, 10), frequency=0.18, angle_bias=0.5, seed=201)
    cv2.imwrite(str(OUT_DIR / "sample_bob_1.png"), bob_1)

    print(f"Sample images created in: {OUT_DIR.resolve()}")
    print(" - sample_alice_1.png (Alice impression 1)")
    print(" - sample_alice_2.png (Alice impression 2 - Genuine probe)")
    print(" - sample_bob_1.png   (Bob impression 1   - Impostor probe)")

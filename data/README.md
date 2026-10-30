# FVC2002 Dataset

## Access

The FVC2002 dataset is **not included in this repository** due to licensing restrictions.

To obtain it:
1. Visit the [FVC2002 website](http://bias.csr.unibo.it/fvc2002/) and complete the access request form.
2. Read and accept the license terms before downloading.
3. After downloading, extract the dataset into this `data/` directory, following the structure below.

## Expected Structure

```
data/
├── DB1_A/          # FVC2002 DB1 subset A (used for evaluation)
│   ├── 101_1.tif
│   ├── 101_2.tif
│   └── ...
├── DB1_B/          # FVC2002 DB1 subset B (optional)
└── README.md       # This file
```

## License & Citation

All use of FVC2002 data must comply with the original license and must include a proper citation:

> D. Maio, D. Maltoni, R. Cappelli, J.L. Wayman, A.K. Jain,
> "FVC2002: Second Fingerprint Verification Competition",
> Proc. 16th IAPR Int. Conf. on Pattern Recognition, Québec City, Canada, August 11-15, 2002.

## Important

- **Do NOT commit dataset files to git.** The `.gitignore` at the repository root excludes all image files under `data/`.
- Images are loaded read-only during preprocessing. They are never written back or modified.
- Temporary processing artefacts derived from dataset images must be deleted after use (see `src/preprocessing.py`).

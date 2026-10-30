# Fingerprint Biometric Verification System

A secure fingerprint enrollment and verification application built on image enhancement, orientation estimation, and minutiae extraction, based on the paper *Fingerprint Image Enhancement and Extraction of Minutiae and Orientation*. Evaluated on FVC2002 benchmark data.

> **Status:** Planning. This README doubles as the project plan. Assumptions: 4 people, part-time (~10-12 h/week each), 12 weeks. Adjust if different.

## Table of Contents

1. [Overview](#overview)
2. [Scope](#scope)
3. [Objectives and Success Criteria](#objectives-and-success-criteria)
4. [Tech Stack](#tech-stack)
5. [Pipeline](#pipeline)
6. [Project Structure](#project-structure)
7. [Getting Started](#getting-started)
8. [Work Breakdown](#work-breakdown)
9. [Roles](#roles)
10. [Timeline and Milestones](#timeline-and-milestones)
11. [Evaluation Protocol](#evaluation-protocol)
12. [Security Plan](#security-plan)
13. [Testing Strategy](#testing-strategy)
14. [Risk Register](#risk-register)
15. [Governance](#governance)
16. [Deliverables](#deliverables)
17. [Effort Estimate](#effort-estimate)
18. [Next Steps](#next-steps)
19. [Limitations](#limitations)

---

## Overview

The system processes fingerprint images, enhances ridge patterns, estimates orientation, extracts minutiae (ridge endings and bifurcations), generates templates, and verifies whether two impressions come from the same finger. No physical sensor is used; images come from established research datasets.

The main delivery risk is the algorithmic core (faithful paper reproduction, a self-documented matcher, honest FAR/FRR/EER), not the UI. The plan front-loads extraction and matching, treats evaluation as a first-class workstream, and keeps UI and hardening lean until the core works.

## Scope

**In scope**

- Input validation, preprocessing, enhancement, orientation estimation, segmentation, skeletonization, cross-numbering minutiae extraction
- Documented minutiae matcher with similarity score and threshold
- Streamlit app for enrollment and verification; encrypted SQLite template storage; authorized deletion
- Visualizations of enhancement, orientation field, and minutiae
- Evaluation scripts (genuine/impostor pairs, FAR, FRR, EER, timing, confidence intervals) on one FVC2002 subset first
- Automated tests (unit, integration, security), paper-to-code traceability table, report, presentation

**Out of scope**

- Live capture, liveness detection, spoof resistance
- Deep learning (future work only)
- Production deployment, React/Next.js frontend
- FVC2004 (stretch, only after core exit criteria are met)

## Objectives and Success Criteria

| # | Objective | Success criterion |
|---|-----------|-------------------|
| O1 | Implement paper methods | Every stage mapped to a paper section; deviations documented |
| O2 | Working enroll/verify app | Demo: enroll, accept genuine, reject impostor, no errors |
| O3 | Documented matcher | Written spec, defined score, threshold chosen on validation data only |
| O4 | Reproducible evaluation | One command regenerates pairs and metrics; fixed seeds |
| O5 | Honest metrics | FAR, FRR, EER, comparison counts, failed extractions, CIs from real runs only |
| O6 | Security-conscious design | Security tests pass (malformed uploads, unauthorized access, encryption, deletion, logs) |
| O7 | Baseline comparison | Baseline vs improved method on identical test pairs |
| O8 | Documentation | Report, presentation, README, traceability table consistent with results |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python |
| Image processing | OpenCV, scikit-image (skeletonization) |
| Numerics | NumPy, SciPy |
| UI | Streamlit |
| Database | SQLite |
| Template protection | Python `cryptography` library |
| Testing | pytest |
| Visualization | Matplotlib, OpenCV |
| Dataset | FVC2002 (FVC2004 optional) |

Deep learning is deliberately excluded: it would replace the paper's core methodology. React/Next.js is deferred: Streamlit lets the team focus on the algorithm and evaluation first.

## Pipeline

1. Dataset loading
2. Input validation (type, dimensions, size, decoding)
3. Preprocessing (grayscale, normalization)
4. Enhancement (per paper)
5. Orientation estimation (gradient-based)
6. Segmentation and skeletonization
7. Minutiae extraction (cross-numbering) and spurious removal
8. Template generation
9. Enrollment (encrypted storage, access control)
10. Verification (alignment, one-to-one correspondence, score)
11. Decision (threshold from validation data)
12. Evaluation and reporting (FAR, FRR, EER, timing; no sensitive templates exposed)

## Project Structure

```
fingerprint-biometric-system/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── data/
│   └── README.md
├── src/
│   ├── preprocessing.py
│   ├── enhancement.py
│   ├── orientation.py
│   ├── minutiae_extraction.py
│   ├── template.py
│   ├── matching.py
│   ├── enrollment.py
│   ├── verification.py
│   ├── database.py
│   └── security.py
├── evaluation/
│   ├── generate_pairs.py
│   ├── evaluate.py
│   └── metrics.py
├── tests/
│   ├── test_preprocessing.py
│   ├── test_minutiae.py
│   ├── test_matching.py
│   ├── test_database.py
│   └── test_security.py
└── reports/
    └── results/
```

Keep the dataset outside version control if its license restricts redistribution.

## Getting Started

> To be completed as the project is built. Planned workflow:

```bash
# 1. Create environment and install pinned dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Place the dataset under data/ (see data/README.md; check license and citation terms)

# 3. Run tests
pytest

# 4. Launch the app
streamlit run app.py

# 5. Run the evaluation
python evaluation/generate_pairs.py
python evaluation/evaluate.py
```

## Work Breakdown

| WP | Name | Key tasks |
|----|------|-----------|
| WP1 | Setup and governance | Repo, CI, structure, pinned config, dataset access and license check, risk register, decision log |
| WP2 | Paper analysis | Extract every step and parameter; list ambiguities; define deviation convention |
| WP3 | Image pipeline | Validation, normalization, enhancement, orientation, segmentation, skeletonization |
| WP4 | Minutiae and template | Cross-numbering, spurious removal, minutiae orientation, template format |
| WP5 | Matching | Matcher design doc, implementation, synthetic-template tests, tuning on dev data |
| WP6 | Evaluation | Identity-disjoint partitions, pair generation, metrics, baseline/improved/final runs |
| WP7 | Application and security | DB layer, encryption, access control, deletion, services, Streamlit UI, log hygiene |
| WP8 | Testing | Unit, integration, security tests |
| WP9 | Documentation | Traceability table, report, presentation, packaging |

## Roles

| Role | Responsibilities | Reviews |
|------|------------------|---------|
| Project lead and integration (A) | Planning, tracking, risks, repo/CI, integration, report assembly | Evaluation |
| Image-processing lead (B) | WP2, WP3, visualizations, traceability | Minutiae |
| Minutiae and matching lead (C) | WP4, WP5, matcher spec | Image pipeline |
| Evaluation, security, app lead (D) | WP6, WP7, WP8 | Matching |

Technical decisions belong to the owning lead and are logged. Scope, protocol, or threshold changes need whole-team agreement and are never made after viewing final test results.

## Timeline and Milestones

| Week | Focus | Outputs |
|------|-------|---------|
| 1 | Setup, paper analysis | Repo, CI, risk register, dataset requested, parameter list |
| 2 | Validation, preprocessing, enhancement start | preprocessing.py with tests; dataset in hand |
| 3 | Enhancement, orientation | enhancement.py, orientation.py |
| 4 | Segmentation, skeletonization, minutiae | Cross-numbering on samples |
| 5 | Cleanup, template | **M1: extraction pipeline demo** |
| 6 | Matcher | matching.py with synthetic tests |
| 7 | Evaluation harness | **M2: baseline results (dev partition)** |
| 8 | App, DB, security | Encrypted storage, deletion, Streamlit UI |
| 9 | Improvement, threshold | **M3: feature freeze, threshold frozen** |
| 10 | Final evaluation, testing | Single final test run; security and integration tests |
| 11 | Documentation | Report and presentation drafts, traceability complete |
| 12 | Buffer, delivery | **M4: final delivery** |

| Milestone | Exit criteria |
|-----------|---------------|
| M0 (end wk 1) | Roles agreed, repo live, dataset requested, parameter list drafted |
| M1 (end wk 5) | Enhanced image, orientation field, skeleton, minutiae overlay on 20+ varied images; unit tests pass; peer visual review |
| M2 (end wk 7) | Matcher tested; baseline FAR/FRR/EER on dev partition with documented protocol |
| M3 (end wk 9) | Threshold chosen on validation data; enroll/verify/delete works; no new features |
| M4 (end wk 12) | Final test results reported once; all tests pass; all deliverables delivered |

**Critical path:** dataset access, paper parameters, enhancement and orientation, skeleton and minutiae, matcher, evaluation harness, threshold selection, final test run, report.
**Parallel work:** database, encryption, and access control (weeks 3-6, using synthetic templates); matcher unit tests on synthetic minutiae.
**If M1 slips more than one week:** defer Streamlit polish and improvement work, not evaluation.

**Definition of done:** code reviewed by a second person, tests passing, parameters in `config.py` and the traceability table, no sensitive data in logs.

## Evaluation Protocol

1. **Partition by identity.** All impressions of a finger stay in the same set; commit the split file.
2. **Development set** for tuning and threshold selection. **Test set** touched once, after M3.
3. **Genuine pairs:** all unordered impression pairs per finger (28 per finger for 8 impressions). **Impostor pairs:** a defined, seeded sample, with counts reported.
4. **Threshold:** chosen on development data (e.g. at EER or a target FAR), applied unchanged to the test set.
5. **Report:** FAR, FRR, EER, genuine and impostor counts, failed extractions (and how counted), bootstrap CIs, mean processing time for extraction and comparison.
6. **No figures** (accuracy, FAR, EER) appear in any document until the experiments have been run. Software test results are reported separately from biometric results.
7. If the official FVC2002 protocol is used instead, document how it was applied and how the threshold was set.

## Security Plan

| Control | Implementation | Verification |
|---------|----------------|--------------|
| Input validation | File-type allowlist, size and dimension limits, safe decode | Corrupt, oversized, wrong-extension, zero-byte file tests |
| Template encryption | `cryptography` authenticated encryption; key stored outside DB | Blobs not plaintext; wrong key fails cleanly |
| Access control | Admin-only management and deletion | Unauthorized-attempt tests |
| Log hygiene | Logging helper rejects images, templates, keys | Log inspection after full enroll/verify/delete cycle |
| Deletion | Remove from DB, temp files, app-managed storage | No residual data; failure handling tested |
| Demo identities | Synthetic IDs only | Review checklist |
| Dataset licensing | Data outside version control; citation included | Pre-submission checklist |

## Testing Strategy

- **Unit:** validation, normalization, orientation on synthetic ridges of known angle, cross-numbering on hand-built skeletons, matcher on known transformed templates
- **Integration:** enroll, verify genuine, verify impostor, delete via the service layer
- **Security:** per the table above
- **Regression:** fixed sample images with stored expected minutiae counts
- **Review:** every PR reviewed by another member; weekly working-software demo
- **Visual verification:** each stage reviewed on 20+ images, including poor-quality ones

## Risk Register

| # | Risk | L | I | Mitigation |
|---|------|---|---|------------|
| R1 | Dataset access delayed or restricted | M | H | Request in week 1; fallback dataset ready; confirm license early |
| R2 | Paper omits parameters | H | M | Record assumptions as deviations; tune on dev data only |
| R3 | Spurious minutiae on low-quality images | H | H | Quality mask, border exclusion, spur/bridge removal; report failed extractions |
| R4 | Matcher underperforms | M | H | Start simple and documented; budget week 9 for justified improvements; report honestly |
| R5 | Evaluation leakage | M | H | Frozen partition, single final test run, review gate before M4 |
| R6 | Pairwise evaluation too slow | M | M | Cache templates; extract once, compare many; profile early |
| R7 | Scope creep | H | M | Stretch work only after M3; log and approve changes |
| R8 | Member unavailable | M | H | Pair reviews, shared decision log, cross-training |
| R9 | Superficial security | M | M | Written threat model; a test per control; explicit limitations |
| R10 | Dependency issues | L | M | Pinned versions, CI on clean environment |

*L = likelihood, I = impact (H/M/L).*

## Governance

| Cadence | Activity | Output |
|---------|----------|--------|
| 2x weekly (15 min) | Standup | Updated task board |
| Weekly (45 min) | Planning, demo, risk review | Decision log and risk register |
| Per milestone | Gate review | Go/no-go note |
| Fortnightly | Supervisor check-in | Feedback in decision log |

Tools: Git hosting with PRs and CI, Kanban board (Backlog, In Progress, Review, Done), shared decision log. Evaluation protocol changes after M3 require unanimous agreement and must be disclosed in the report.

## Deliverables

| # | Deliverable | Due |
|---|-------------|-----|
| D1 | Working enrollment and verification application | Week 9 |
| D2 | Paper-faithful enhancement, orientation, minutiae extraction | Week 5 |
| D3 | Visualizations of enhancement, orientation, minutiae | Week 5 |
| D4 | Matching algorithm document and threshold procedure | Week 7 |
| D5 | Dataset preparation and evaluation scripts | Week 7 |
| D6 | Results report (FAR, FRR, EER, timing, CIs) | Week 10 |
| D7 | Software, integration, and security tests | Week 10 |
| D8 | Paper-to-code traceability table | Week 11 |
| D9 | Project report and presentation | Week 12 |

## Effort Estimate

| Work package | Person-hours |
|--------------|--------------|
| WP1 Setup and governance | 25 |
| WP2 Paper analysis | 30 |
| WP3 Image pipeline | 120 |
| WP4 Minutiae and template | 90 |
| WP5 Matching | 80 |
| WP6 Evaluation | 80 |
| WP7 Application and security | 90 |
| WP8 Testing | 50 |
| WP9 Documentation | 90 |
| Management and contingency (~10%) | 55 |
| **Total** | **~710** |

Capacity is about 575 hours (4 people x 12 h x 12 weeks), so the estimate exceeds capacity. Treat WP3-WP5 as the main schedule risk and cut Streamlit polish and improvement work first if hours run short, or extend the timeline or team.

## Next Steps

1. Hold kickoff; confirm roles, team size, and duration.
2. Submit the FVC2002 access request; record license and citation terms.
3. Create the repo, CI, and folder structure.
4. Complete the paper parameter and ambiguity list; agree the deviation convention.
5. Ask the supervisor to confirm the evaluation protocol (own partitioning vs official FVC).
6. Select 10-20 representative sample images (clean, dry, wet, low-contrast).
7. Implement and test input validation; start enhancement.
8. Draft the threat model and risk register.

## Limitations

Minutiae matching provides no liveness detection or spoof resistance, and the prototype does not demonstrate live acquisition. The security measures make the prototype security-conscious but do not guarantee the absence of vulnerabilities.

## Delivery Principles

- **Core before cosmetics:** rigorous evaluation beats a polished UI on unverified results.
- **One source of truth for parameters:** all tunables in `config.py`, traced to the paper or a documented deviation.
- **Honest reporting:** include failed extractions and modest error rates.
- **Freeze, then test:** fix threshold and method before the single final test run.
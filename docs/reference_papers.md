# TrustMedia — Reference Papers Guide

## Primary Reference Paper (Show This to Your Examiner)

> **"AVoiD-DF: Audio-Visual Joint Learning for Detecting Deepfake"**
> Zhang et al., IEEE Transactions on Information Forensics and Security (TIFS), 2023
> DOI: `10.1109/TIFS.2023.3262549`

**Why this is your primary reference:**
- Audio-visual joint deepfake detection — your exact problem
- Lip-sync inconsistency detection — your `lipsync_analyzer` branch
- Cross-modal attention fusion — your `FusionModel` with `ModalityGate`
- Published in IEEE TIFS — the top venue for this topic

**Your project in one sentence:**
> TrustMedia = AVoiD-DF + physiological signals (blink EAR + head motion) + calibrated uncertainty + blockchain provenance

### Where to Find It

| Source | How |
|---|---|
| **IEEE Xplore** (official) | `ieeexplore.ieee.org` → search `AVoiD-DF` or paste DOI |
| **Google Scholar** (free PDF) | Search: `AVoiD-DF Audio-Visual Joint Learning Detecting Deepfake Zhang 2023` |
| **arXiv** (free preprint) | `arxiv.org` → search `AVoiD-DF deepfake` |
| **Semantic Scholar** | `semanticscholar.org` → search `AVoiD-DF` |
| **ResearchGate** | `researchgate.net` → search the full title |

> If your college has IEEE access, use your institutional login at IEEE Xplore for the full paper.

---

## Papers to Avoid (Wrong Scope)

| arXiv ID | Authors | Why It Doesn't Fit |
|---|---|---|
| `2209.13792` | Lacerda et al. | 4-page workshop paper, face-only, no audio, no fusion |
| `2205.00753` | Guo et al. | Residual-domain image forensics, no audio/video, no multimodal |

Both are **image-level** detection. Your project is **video + audio + physiological signals**.

---

## Component-by-Component Paper Mapping

| Your Component | Reference Paper |
|---|---|
| EfficientNet-B4 + Temporal Transformer (face branch) | Li et al., *"Face X-ray for More General Face Forgery Detection"*, CVPR 2020 |
| SyncNet-style lip-sync (ResNet18 + Audio CNN) | Chung & Zisserman, *"Out of time: automated lip sync in the wild"*, ACCV 2016 |
| Wav2Vec2 + MFCC (voice branch) | Yi et al., *"ADD 2022: The First Audio Deep Synthesis Detection Challenge"*, 2022 |
| MediaPipe EAR + blink features | Pan et al., *"Eyeblink-based Anti-Spoofing in Face Recognition"*, ICCV 2007 |
| solvePnP head motion | Ruiz et al., *"Fine-Grained Head Pose Estimation Without Keypoints"*, CVPRW 2018 |
| Attention MLP Fusion with ModalityGate | Zhang et al., *"AVoiD-DF"*, IEEE TIFS 2023 ← **primary ref** |
| Temperature Scaling calibration | Guo et al., *"On Calibration of Modern Neural Networks"*, ICML 2017 |
| Blockchain provenance (Polygon) | Novel contribution — no direct prior paper |

---

## Free arXiv Papers That Match Your Project

Search these IDs directly on `arxiv.org`:

| arXiv ID | Title / Why It Fits |
|---|---|
| `2108.05080` | **FakeAVCeleb** — multimodal audio+video deepfake dataset; face+voice+lipsync modalities ← **best free alternative to AVoiD-DF** |
| `2209.00773` | Multimodal deepfake: audio + visual fusion |
| `2212.14184` | Audio-visual synchronization for forgery detection |
| `2203.05178` | Fusion of multiple cues for deepfake detection |
| `1706.04599` | Guo et al., *"On Calibration of Modern Neural Networks"* — your Temperature Scaling |

---

## Your Novelty Over AVoiD-DF (Key for Examiner)

| What AVoiD-DF Has | What TrustMedia Adds |
|---|---|
| Face + Voice + LipSync (3 modalities) | + Blink EAR + HeadMotion (5 modalities total) |
| Binary fake/real output | Calibrated uncertainty flag (LOW / MEDIUM / HIGH) + entropy |
| No physiological signals | MediaPipe blink rate, EAR stats, solvePnP physics-based head motion |
| No provenance | Blockchain audit trail on Polygon — on-chain hash per detection |
| No modality robustness | Modality dropout (20%) during fusion training |

---

## Copy-Paste Citation List

```
[1] Zhang et al., "AVoiD-DF: Audio-Visual Joint Learning for Detecting Deepfake,"
    IEEE Trans. Inf. Forensics Security, 2023. DOI: 10.1109/TIFS.2023.3262549

[2] Chung & Zisserman, "Out of time: automated lip sync in the wild,"
    Asian Conf. Computer Vision (ACCV), 2016.

[3] Li et al., "Face X-ray for More General Face Forgery Detection,"
    IEEE/CVF CVPR, 2020.

[4] Guo et al., "On Calibration of Modern Neural Networks,"
    ICML, 2017. arXiv:1706.04599

[5] Rossler et al., "FaceForensics++: Learning to Detect Manipulated Facial Images,"
    IEEE/CVF ICCV, 2019.   ← benchmark dataset

[6] Li et al., "Celeb-DF: A Large-Scale Challenging Dataset for DeepFake Forensics,"
    IEEE/CVF CVPR, 2020.   ← benchmark dataset

[7] Khalid et al., "FakeAVCeleb: A Novel Audio-Video Multimodal Deepfake Dataset,"
    NeurIPS Workshop, 2021. arXiv:2108.05080
```

---

## Suggested Paper Title for TrustMedia

> *"TrustMedia: Multimodal Deepfake Detection with Physiological Signal Integration and Blockchain Provenance"*

### Abstract Structure (Template)

1. **Problem** — Deepfake videos pose a growing threat; existing detectors use 2–3 modalities and produce uncalibrated binary outputs
2. **Gap** — No prior work combines physiological signals (blink, head motion) with audio-visual fusion and tamper-evident provenance
3. **Method** — 5-branch expert fusion (face, lipsync, voice, blink, headmotion) with attention MLP + temperature scaling; on-chain result hashing via Polygon
4. **Novelty** — Uncertainty-aware output (entropy + flag), modality dropout for robustness, blockchain audit trail
5. **Results** — Evaluated on FaceForensics++, Celeb-DF, FakeAVCeleb; outperforms AVoiD-DF baseline

---

## Recommended Submission Venues

| Venue | Type | Fit |
|---|---|---|
| **IEEE TIFS** | Journal | Best topic fit; where AVoiD-DF was published |
| **ACM MM** | Conference | Best for multimodal + blockchain angle |
| **IEEE FG** | Conference | Best for face + blink + headmotion work |
| **IEEE ICASSP** | Conference | Best if voice + lipsync is primary novelty |
| **Pattern Recognition Letters** | Journal | Shorter format, faster review |

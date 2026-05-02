# Multimodal Deepfake Detection Pipeline — Upgrade Guide

## Overview

This system detects deepfake videos using **5 independent expert models** fused by an attention-based neural network.

### Output Fields
```json
{
  "final_label": "AUTHENTIC | MANIPULATED",
  "fake_probability": 72.3,
  "per_signal_scores": {
    "face_score": 80.1,
    "lipsync_score": 65.2,
    "voice_score": 45.0,
    "blink_score": 30.0,
    "headmotion_score": 55.0
  },
  "explanation": "Face artifacts high (80%), Lip-sync mismatch moderate (65%)",
  "confidence_calibrated_probability": 74.1,
  "uncertainty_flag": "LOW",
  "entropy": 0.22,
  "modality_weights": {"face": 0.30, "lipsync": 0.22, "voice": 0.22, "blink": 0.13, "headmotion": 0.13},
  "fusion_method": "attention_fusion_calibrated"
}
```

---

## Architecture

```
VIDEO (.mp4/.mov)
       |
       |── FFmpeg ──> frames (10 FPS, max 90) + audio (16kHz mono WAV)
       |
       |── [A] Face Branch       EfficientNet-B4 + Temporal Transformer ──> face_score
       |── [B] Lip-Sync Branch   SyncNet-style (ResNet18 + Audio CNN)   ──> lipsync_score
       |── [C] Voice Branch      Wav2Vec2 + MFCC CNN classifier          ──> voice_score
       |── [D] Blink Branch      MediaPipe EAR + XGBoost                 ──> blink_score
       |── [E] Head Motion       solvePnP + Physics + XGBoost            ──> headmotion_score
       |
       └── [F] Fusion            Attention MLP + Temperature Scaling     ──> fake_probability
                                                                          + uncertainty_flag
                                                                          + explanation
```

---

## Setup

### 1. Install dependencies
```bash
cd services/api
pip install -r requirements.txt

# Additional ML training dependencies
pip install xgboost scikit-learn tqdm pyyaml
```

### 2. Verify FFmpeg is installed
```bash
ffmpeg -version
```

### 3. Run inference immediately (uses heuristic fallback without trained weights)
```bash
python scripts/predict.py --video path/to/video.mp4
```

---

## Training (Step-by-Step)

### Step 0: Prepare dataset manifest
```bash
python ml/datasets/prepare_manifest.py \
  --ff_root /data/FaceForensics++ \
  --celeb_root /data/Celeb-DF \
  --output data/manifest.json \
  --train 0.70 --val 0.15
```

Dataset structure expected:
- **FaceForensics++**: `ff_root/original_sequences/` + `ff_root/manipulated_sequences/`
- **Celeb-DF v2**: `celeb_root/Celeb-real/` + `celeb_root/Celeb-synthesis/`
- **Generic**: any folder with `real/` and `fake/` subfolders

### Step 1: Train Face Branch (GPU recommended, ~30 epochs)
```bash
python scripts/train_face.py \
  --manifest data/manifest.json \
  --config ml/configs/config.yaml

# Best checkpoint saved to: weights/face/best.pt
```

### Step 2: Train Voice Branch
```bash
python scripts/train_voice.py \
  --manifest data/manifest.json \
  --config ml/configs/config.yaml

# Best checkpoint: weights/voice/best.pt
```

### Step 3: Train Lip-Sync Branch
```bash
python scripts/train_lipsync.py \
  --manifest data/manifest.json \
  --config ml/configs/config.yaml

# Best checkpoint: weights/lipsync/best.pt
```

### Step 4: Train Blink Classifier
```bash
python scripts/train_blink.py \
  --manifest data/manifest.json \
  --config ml/configs/config.yaml

# Saved to: weights/blink/blink_classifier.joblib
```

### Step 5: Train Head Motion Classifier
```bash
python scripts/train_headmotion.py \
  --manifest data/manifest.json \
  --config ml/configs/config.yaml

# Saved to: weights/headmotion/headmotion_classifier.joblib
```

### Step 6: Extract expert scores for fusion training
```bash
# First run inference on all training/val videos to collect expert scores
python scripts/predict.py --video ... 
# Or use the batch extraction helper (see scripts/extract_expert_scores.py)
```

### Step 7: Train Fusion Model
```bash
python scripts/train_fusion.py \
  --manifest data/manifest.json \
  --config ml/configs/config.yaml \
  --scores_cache data/expert_scores \
  --score_only    # use simpler fusion when no embeddings available

# Best checkpoint: weights/fusion/best.pt
# Temperature:    weights/fusion/temperature.pt
```

---

## Inference

### Standalone CLI
```bash
python scripts/predict.py --video video.mp4
python scripts/predict.py --video video.mp4 --output result.json
python scripts/predict.py --video video.mp4 --quiet  # JSON only to stdout
```

### FastAPI endpoint (existing)
```bash
curl -X POST http://localhost:8000/api/v1/videos/upload \
  -F "file=@video.mp4"
```

### Python API
```python
from scripts.predict import run_predict
result = run_predict("video.mp4", verbose=True)
print(result["final_label"])          # AUTHENTIC or MANIPULATED
print(result["fake_probability"])     # 0-100
print(result["uncertainty_flag"])     # LOW/MEDIUM/HIGH
print(result["explanation"])          # human-readable
```

---

## Evaluation

```bash
# Test set evaluation with full metrics
python scripts/evaluate.py \
  --manifest data/manifest.json \
  --split test

# Output: data/eval_test_results.json
# Includes: Accuracy, Precision, Recall, F1, AUC-ROC, EER, ECE
# + Cross-dataset breakdown
# + Ablation study (each modality contribution)
```

---

## Improving Accuracy

### When face_score is unreliable
- **Problem**: Low-resolution videos, heavy compression, dark lighting
- **Fix**: Increase `data.face_margin` in config.yaml (try 0.4–0.5)
- **Fix**: Add more compressed training samples (augmentations.compression_crf_range: [15, 45])
- **Fix**: Train with additional data from DFDC (highly compressed)

### When lipsync_score is noisy
- **Problem**: Silent videos or mumbling speakers
- **Fix**: The score defaults to 50.0 (neutral) for silent videos automatically
- **Fix**: Train lipsync branch on FakeAVCeleb dataset (audio-visual deepfakes)

### When voice_score misclassifies
- **Problem**: Accented speech, background noise
- **Fix**: Use ECAPA-TDNN embeddings instead of wav2vec2 for speaker verification
- **Fix**: Add spectral augmentation: `librosa.effects.preemphasis`, pitch shifting

### When blink detection fails
- **Problem**: Sunglasses, profile view, very dark eyes
- **Fix**: The EAR method falls back to 0.25 (neutral) when face not detected
- **Fix**: Retrain with more edge-case videos

### When uncertainty is always HIGH
- **Problem**: Expert models disagree too much
- **Fix**: Collect more training data where all signals agree
- **Fix**: Use hard negative mining: find videos where model is confidently wrong

### General accuracy improvements
1. **More data**: Each additional 1000 training videos typically +1-2% AUC
2. **Hard negative mining**: After initial training, find failures and retrain
3. **Label smoothing**: Already 0.1 — increase to 0.15 if overconfident
4. **Ensemble**: Train 3 face models with different seeds, average predictions

---

## Troubleshooting

### No face detected
- Score defaults to **50.0** (uncertain, not 0 or 100)
- Check: video resolution ≥ 240p, face occupies ≥ 5% of frame area
- Solution: Use `min_face_size=20` in MTCNN for very small faces

### Silent video (no audio track)
- voice_score and lipsync_score both default to **50.0**
- The fusion model is trained with modality dropout so it handles this gracefully
- uncertainty_flag will be set to **MEDIUM** or **HIGH**

### Multiple faces in frame
- The pipeline always picks the **largest face** in each frame
- For group videos: uncertainty will be HIGH; consider pre-cropping to single face

### Low light / dark video
- EfficientNet handles this better than heuristics
- Use `color_jitter: brightness: [0.5, 1.5]` in training augmentations

### Heavy compression (low bitrate)
- Train with `compression_crf_range: [10, 51]` for maximum robustness
- The face model should still work with JPEG quality ≥ 30

### Very short videos (<3 seconds)
- voice_score returns 50.0 (too short for reliable analysis)
- blink_score may be 50.0 (not enough blink events)
- lipsync_score still works with ≥5 frames

### GPU out of memory (CUDA OOM)
- Reduce batch_size in config.yaml (face.batch_size: 4)
- Use fp16: add `--fp16` flag or set `torch.cuda.amp.autocast`

---

## Folder Structure

```
finalyear/
├── ml/
│   ├── configs/config.yaml          # Master training config
│   ├── models/
│   │   ├── face_model.py            # EfficientNet-B4 + Temporal Transformer
│   │   ├── lipsync_model.py         # SyncNet-style AV sync model
│   │   ├── voice_model.py           # Wav2Vec2 + MFCC classifier
│   │   ├── blink_model.py           # EAR extraction + XGBoost
│   │   ├── headmotion_model.py      # Pose physics + XGBoost
│   │   └── fusion_model.py          # Attention-based fusion + calibration
│   ├── datasets/
│   │   ├── base_dataset.py          # Dataset + augmentation + balanced sampler
│   │   └── prepare_manifest.py      # Dataset manifest generator
│   ├── training/
│   │   ├── losses.py                # FocalLoss, ContrastiveLoss, LabelSmoothing
│   │   └── trainer_utils.py         # Seed, EarlyStopping, checkpoints, metrics
│   └── calibration/
│       └── calibrator.py            # Temperature scaling, ECE, EER
├── scripts/
│   ├── train_face.py                # Train face branch
│   ├── train_voice.py               # Train voice branch
│   ├── train_lipsync.py             # Train lipsync branch
│   ├── train_blink.py               # Train blink classifier
│   ├── train_headmotion.py          # Train head motion classifier
│   ├── train_fusion.py              # Train fusion model + calibrate
│   ├── predict.py                   # Standalone inference CLI
│   └── evaluate.py                  # Full evaluation + ablation
├── weights/
│   ├── face/best.pt                 # Face branch checkpoint
│   ├── lipsync/best.pt              # Lip-sync checkpoint
│   ├── voice/best.pt                # Voice checkpoint
│   ├── blink/blink_classifier.joblib
│   ├── headmotion/headmotion_classifier.joblib
│   └── fusion/best.pt + temperature.pt
└── services/api/app/services/ai/
    ├── pipeline.py                  # Orchestrates all 5 branches
    ├── face_detector.py             # Face branch inference
    ├── lipsync_analyzer.py          # Lip-sync inference
    ├── voice_analyzer.py            # Voice inference
    ├── blink_detector.py            # Blink inference
    ├── headmotion_analyzer.py       # Head motion inference (NEW)
    └── fusion.py                    # Upgraded attention fusion
```

---

## Deployment

The existing Docker Compose setup works unchanged. The new ML models are loaded lazily on first request.

```bash
docker-compose up --build
```

For GPU inference:
```bash
# In .env
MODEL_DEVICE=cuda
```

For production mode (more frames):
```bash
DEMO_MODE=false
```

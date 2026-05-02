"""
Face Artifact + Temporal Branch — Production Inference.

Replaces heuristic approach with EfficientNet-B4 + Temporal Transformer.
Falls back to heuristic if trained weights not found.
"""
from __future__ import annotations
import os, sys, cv2, numpy as np, torch
from PIL import Image
from app.core.config import get_settings

settings = get_settings()

_WEIGHTS = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "../../../../../weights/face/best.pt"
))

_face_model = None
_mtcnn = None
_model_loaded = False


def _get_mtcnn():
    global _mtcnn
    if _mtcnn is None:
        from facenet_pytorch import MTCNN
        _mtcnn = MTCNN(keep_all=True, device=torch.device(settings.model_device),
                       select_largest=False, min_face_size=40)
    return _mtcnn


def _get_face_model():
    global _face_model, _model_loaded
    if _model_loaded:
        return _face_model
    _model_loaded = True
    if not os.path.exists(_WEIGHTS):
        return None
    try:
        root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../../"))
        if root not in sys.path:
            sys.path.insert(0, root)
        from ml.models.face_model import FaceTemporalModel
        model = FaceTemporalModel(backbone="efficientnet_b4", temporal="transformer", pretrained=False)
        ckpt = torch.load(_WEIGHTS, map_location="cpu")
        model.load_state_dict(ckpt["model_state"])
        model.eval().to(settings.model_device)
        _face_model = model
        return model
    except Exception as exc:
        print(f"[face_detector] model load failed: {exc}")
        return None


def _align_crop(img_cv, box, size=224):
    x1, y1, x2, y2 = [int(c) for c in box]
    m = int((y2 - y1) * 0.3)
    x1 = max(0, x1-m); y1 = max(0, y1-m)
    x2 = min(img_cv.shape[1], x2+m); y2 = min(img_cv.shape[0], y2+m)
    crop = img_cv[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB), (size, size))


def _frame_texture_score(img_cv):
    """
    Analyze a single frame for GAN/diffusion artifact signatures.

    AI-generated faces show:
      - Unnatural frequency distribution (GAN checkerboard, diffusion blur)
      - Low high-freq energy in face region (over-smoothed skin texture)
      - Inconsistent noise floor between face and background
      - Spectral peak at aliasing frequencies

    Returns artifact score 0-100 (higher = more AI-like).
    """
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape

    # DCT-based frequency analysis on 8x8 blocks (like JPEG artifact analysis)
    scores = []
    block = 64
    for y in range(0, h - block, block):
        for x in range(0, w - block, block):
            patch = gray[y:y+block, x:x+block]
            dct = cv2.dct(patch / 255.0)
            # High-freq energy ratio: real images have natural roll-off
            # GANs often have flat or spiky high-freq response
            low_e  = float(np.sum(dct[:8, :8] ** 2))
            high_e = float(np.sum(dct[32:, 32:] ** 2))
            total  = low_e + high_e + 1e-8
            hf_ratio = high_e / total
            scores.append(hf_ratio)

    if not scores:
        return 50.0

    hf_mean = float(np.mean(scores))
    hf_std  = float(np.std(scores))

    # GAN images: unnaturally low high-freq energy (over-smooth) OR
    #             unnaturally high (checkerboard artifacts)
    # Real camera images: moderate, consistent high-freq energy
    if hf_mean < 0.015:
        # Extreme smoothing — GAN or heavy blur
        freq_score = 70.0
    elif hf_mean > 0.12:
        # Checkerboard / aliasing artifacts
        freq_score = 65.0
    elif hf_mean < 0.03:
        freq_score = 50.0
    elif hf_mean < 0.06:
        freq_score = 25.0
    else:
        freq_score = 10.0

    # Inconsistent block variance (real images have spatially coherent texture)
    if hf_std > 0.06:
        freq_score = min(freq_score + 20, 100)

    return float(freq_score)


def _heuristic_score(frame_paths):
    mtcnn = _get_mtcnn()
    face_counts, boundary_scores, color_diffs, texture_scores = [], [], [], []

    for path in frame_paths[:30]:
        img_cv = cv2.imread(path)
        if img_cv is None:
            continue
        img_pil = Image.open(path).convert("RGB")

        # Always compute frame-level texture score (works even without face detection)
        texture_scores.append(_frame_texture_score(img_cv))

        try:
            boxes, _ = mtcnn.detect(img_pil)
        except Exception:
            boxes = None

        if boxes is not None:
            face_counts.append(len(boxes))
            largest = max(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]))
            x1,y1,x2,y2 = [max(0,int(c)) for c in largest]
            x2 = min(img_cv.shape[1],x2); y2 = min(img_cv.shape[0],y2)
            face_region = img_cv[y1:y2, x1:x2]
            if face_region.size > 0:
                bw = max(2, min(face_region.shape[:2])//10)
                mask = np.zeros(face_region.shape[:2], dtype=np.uint8)
                mask[:bw,:]=mask[-bw:,:]=mask[:,:bw]=mask[:,-bw:]=255
                gray_f = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
                lap = cv2.Laplacian(gray_f, cv2.CV_64F)
                if mask.sum() > 0:
                    boundary_scores.append(float(np.var(lap[mask>0])))
                pad = 20
                bg = img_cv[max(0,y1-pad):min(img_cv.shape[0],y2+pad),
                             max(0,x1-pad):min(img_cv.shape[1],x2+pad)]
                if bg.size > 0:
                    fh = cv2.calcHist([face_region],[0,1,2],None,[8,8,8],[0,256]*3)
                    bh = cv2.calcHist([bg],[0,1,2],None,[8,8,8],[0,256]*3)
                    cv2.normalize(fh,fh); cv2.normalize(bh,bh)
                    color_diffs.append(cv2.compareHist(fh,bh,cv2.HISTCMP_BHATTACHARYYA))
        else:
            face_counts.append(0)

    no_face = (not face_counts or max(face_counts) == 0)
    if no_face:
        return {"face_score": 50.0, "embedding": None, "details": {"note": "No faces detected"}}

    ba = float(np.mean(boundary_scores)) if boundary_scores else 100.0
    ca = float(np.mean(color_diffs)) if color_diffs else 0.3

    # ── Boundary artifact signal ──────────────────────────────────────────
    # Only flag extreme over-smoothing (GAN) or compression artefacts
    if ba < 20:
        ba_score = 60.0
    elif ba > 800:
        ba_score = 50.0
    else:
        ba_score = 0.0

    # ── Color inconsistency ───────────────────────────────────────────────
    ca_score = max(0.0, min(100.0, (ca - 0.45) * 250))

    # ── Multi-face detection (strongest signal for portrait deepfakes) ────
    # Single-speaker real video: exactly 1 face per frame consistently.
    # MTCNN detects ghost faces from deepfake compositing edges/artifacts.
    multi_face_ratio = float(np.mean([1.0 if c > 1 else 0.0 for c in face_counts]))
    mf_score = min(100.0, multi_face_ratio * 180.0)

    # ── Face count variance ───────────────────────────────────────────────
    # Jumping between 1→3→2 face detections = unstable generation artifacts
    cv_ = float(np.std(face_counts)) if len(face_counts) > 1 else 0.0
    cv_score = min(100.0, cv_ * 35.0)

    # Multi-face and variance are the reliable discriminators here
    score = (0.10 * ba_score + 0.05 * ca_score + 0.55 * mf_score + 0.30 * cv_score)

    return {
        "face_score": round(score, 2),
        "embedding": None,
        "details": {
            "method": "heuristic_mtcnn",
            "boundary_artifact_avg": round(ba, 3),
            "color_inconsistency_avg": round(ca, 3),
            "multi_face_ratio": round(multi_face_ratio, 3),
            "face_count_std": round(cv_, 3),
        }
    }


def analyze_faces(frame_paths: list[str]) -> dict:
    """Analyze frames for face manipulation. Returns face_score (0-100), embedding, details."""
    if not frame_paths:
        return {"face_score":50.0,"embedding":None,"details":{"note":"No frames"}}

    model = _get_face_model()
    if model is None:
        return _heuristic_score(frame_paths)

    mtcnn = _get_mtcnn()
    device = torch.device(settings.model_device)
    face_crops = []
    faces_found = 0

    for path in frame_paths:
        img_cv = cv2.imread(path)
        if img_cv is None:
            continue
        img_pil = Image.open(path).convert("RGB")
        boxes, _ = mtcnn.detect(img_pil)
        if boxes is None:
            continue
        faces_found += 1
        box = max(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]))
        crop = _align_crop(img_cv, box)
        if crop is not None:
            t = torch.from_numpy(crop).permute(2,0,1).float()/255.0
            face_crops.append(t)

    if len(face_crops) < 4:
        return {"face_score":50.0,"embedding":None,
                "details":{"note":f"Too few faces ({faces_found}/{len(frame_paths)} frames)","method":"ml"}}

    target_T = 32
    if len(face_crops) >= target_T:
        idx = np.linspace(0, len(face_crops)-1, target_T, dtype=int)
        clips = [torch.stack([face_crops[i] for i in idx])]
    else:
        crops = face_crops + [face_crops[-1]] * (target_T - len(face_crops))
        clips = [torch.stack(crops[:target_T])]

    clip_scores, clip_embs = [], []
    model.eval()
    with torch.no_grad():
        for clip in clips:
            out = model(clip.unsqueeze(0).to(device), return_embedding=True)
            clip_scores.append(torch.sigmoid(out["logit"]).item())
            clip_embs.append(out["embedding"].cpu().numpy()[0])

    mean_prob = float(np.mean(clip_scores))
    return {
        "face_score": round(mean_prob * 100, 2),
        "embedding": np.mean(clip_embs, axis=0),
        "details": {
            "method":"ml_efficientnet_transformer",
            "faces_detected_frames": faces_found,
            "total_frames": len(frame_paths),
            "clip_score_std": round(float(np.std(clip_scores)), 4),
        }
    }

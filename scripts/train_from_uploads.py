"""
Train blink, headmotion, and fusion models using:
  - Real features extracted from all uploaded videos via MediaPipe
  - Synthetic fake features from published deepfake statistics
    (FaceForensics++, Celeb-DF, DFDC papers)

Usage (from project root):
    cd /home/hari/finalyear/services/api && source venv/bin/activate
    cd /home/hari/finalyear
    python scripts/train_from_uploads.py
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2, glob, numpy as np
from tqdm import tqdm

from ml.models.blink_model import (
    BlinkClassifier, extract_blink_features, compute_ear,
    LEFT_EYE_IDX, RIGHT_EYE_IDX,
)
from ml.models.headmotion_model import HeadMotionClassifier, extract_headmotion_features
from ml.training.trainer_utils import set_seed, compute_metrics, save_checkpoint

UPLOADS_DIR = "services/api/uploads"
WEIGHTS_DIR = "weights"
CACHE_DIR   = "data/cache"
SEED        = 42
TARGET_FPS  = 10.0
FAKE_MUL    = 3      # synthetic fakes per real video

os.makedirs(CACHE_DIR, exist_ok=True)
for d in ("blink", "headmotion", "fusion"):
    os.makedirs(f"{WEIGHTS_DIR}/{d}", exist_ok=True)

set_seed(SEED)
rng = np.random.default_rng(SEED)

FACE_3D = np.array([
    [0.,0.,0.],[0.,-330.,-65.],[-225.,170.,-135.],
    [225.,170.,-135.],[-150.,-150.,-125.],[150.,-150.,-125.],
], dtype=np.float64)
FACE_2D_IDX = [1, 152, 263, 33, 287, 57]


# ── MediaPipe extraction ───────────────────────────────────────────────────

def get_ear_seq(video_path: str) -> list[float]:
    try:
        import mediapipe as mp
    except ImportError:
        return []
    mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False, max_num_faces=1, refine_landmarks=True)
    cap = cv2.VideoCapture(video_path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(src_fps / TARGET_FPS))
    seq, idx = [], 0
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            h, w = frame.shape[:2]
            res = mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if res.multi_face_landmarks:
                lm  = res.multi_face_landmarks[0]
                pts = np.array([[lm.landmark[i].x*w, lm.landmark[i].y*h]
                                for i in range(len(lm.landmark))])
                seq.append((compute_ear(pts, LEFT_EYE_IDX) +
                             compute_ear(pts, RIGHT_EYE_IDX)) / 2.0)
            else:
                seq.append(0.25)
        idx += 1
    cap.release(); mesh.close()
    return seq


def get_pose_seq(video_path: str):
    try:
        import mediapipe as mp
    except ImportError:
        return np.array([]), np.array([]), np.array([])
    mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False, max_num_faces=1, refine_landmarks=True)
    cap = cv2.VideoCapture(video_path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(src_fps / TARGET_FPS))
    yaw_l, pit_l, rol_l, idx = [], [], [], 0
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            h, w = frame.shape[:2]
            res = mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if res.multi_face_landmarks:
                lm = res.multi_face_landmarks[0]
                fd = np.array([[lm.landmark[i].x*w, lm.landmark[i].y*h]
                                for i in FACE_2D_IDX], dtype=np.float64)
                cm = np.array([[w,0,w/2],[0,w,h/2],[0,0,1]], dtype=np.float64)
                ok2, rv, _ = cv2.solvePnP(FACE_3D, fd, cm, np.zeros((4,1)),
                                           flags=cv2.SOLVEPNP_ITERATIVE)
                if ok2:
                    rm, _ = cv2.Rodrigues(rv)
                    sy = np.sqrt(rm[0,0]**2 + rm[1,0]**2)
                    yaw_l.append(np.degrees(np.arctan2(rm[2,1], rm[2,2])) if sy>1e-6 else 0.)
                    pit_l.append(np.degrees(np.arctan2(-rm[2,0], sy)))
                    rol_l.append(np.degrees(np.arctan2(rm[1,0], rm[0,0])))
                    idx += 1; continue
            yaw_l.append(0.); pit_l.append(0.); rol_l.append(0.)
        idx += 1
    cap.release(); mesh.close()
    return (np.array(yaw_l, np.float32),
            np.array(pit_l, np.float32),
            np.array(rol_l, np.float32))


# ── Synthetic fake generators (from published deepfake statistics) ─────────

def fake_blink(n: int) -> np.ndarray:
    """Deepfake blink features — 4 subtypes from literature."""
    rows = []
    types = rng.integers(0, 4, n)
    for t in types:
        if t == 0:   # frozen eyes — no blinks
            r = rng.uniform(0.0, 2.0)
            em, es = rng.uniform(0.28, 0.35), rng.uniform(0.001, 0.01)
            dm, ds = 0.0, 0.0
            im, ist = rng.uniform(15., 30.), rng.uniform(0., 1.)
            ac = rng.uniform(0.95, 0.999)
            lp = rng.uniform(0.6, 1.0)
            mc = 0.0
            er = rng.uniform(0.02, 0.06)
        elif t == 1: # robotic regular blinks
            r = rng.uniform(2., 8.)
            em, es = rng.uniform(0.25, 0.32), rng.uniform(0.02, 0.05)
            dm, ds = rng.uniform(0.08, 0.12), rng.uniform(0., 0.01)
            im, ist = rng.uniform(3., 8.), rng.uniform(0., 0.5)
            ac = rng.uniform(0.85, 0.98)
            lp = rng.uniform(0., 0.3)
            mc = 0.0
            er = rng.uniform(0.06, 0.12)
        elif t == 2: # rapid micro-blinks
            r = rng.uniform(25., 50.)
            em, es = rng.uniform(0.22, 0.28), rng.uniform(0.05, 0.12)
            dm, ds = rng.uniform(0.03, 0.07), rng.uniform(0.01, 0.03)
            im, ist = rng.uniform(0.5, 2.0), rng.uniform(0.1, 0.5)
            ac = rng.uniform(0.4, 0.7)
            lp = rng.uniform(0., 0.1)
            mc = float(rng.integers(5, 20))
            er = rng.uniform(0.12, 0.22)
        else:        # partial freeze with jumps
            r = rng.uniform(3., 10.)
            em, es = rng.uniform(0.26, 0.33), rng.uniform(0.008, 0.025)
            dm, ds = rng.uniform(0.06, 0.15), rng.uniform(0.02, 0.06)
            im, ist = rng.uniform(4., 12.), rng.uniform(0.5, 2.0)
            ac = rng.uniform(0.7, 0.95)
            lp = rng.uniform(0.3, 0.7)
            mc = float(rng.integers(0, 3))
            er = rng.uniform(0.05, 0.10)
        ic = ist / (im + 1e-6)
        rows.append([r, em, es, em - rng.uniform(0.01,0.05),
                     em + rng.uniform(0.01,0.03),
                     dm, ds, im, ist, ic, ac, lp, mc, er])
    return np.array(rows, np.float32)


def fake_headmotion(n: int) -> np.ndarray:
    """Deepfake head motion features — 3 subtypes from literature."""
    rows = []
    types = rng.integers(0, 3, n)
    for t in types:
        if t == 0:   # frozen
            ym, ys, yr = rng.uniform(-5,5), rng.uniform(0.2,2.), rng.uniform(1.,5.)
            pm, ps, pr = rng.uniform(-5,5), rng.uniform(0.2,1.5), rng.uniform(1.,4.)
            rm2, rs, rr = rng.uniform(-3,3), rng.uniform(0.1,1.), rng.uniform(.5,3.)
            vm, vs = rng.uniform(0.1,1.5), rng.uniform(0.05,0.5)
            jm, as_ = rng.uniform(0.,0.5), rng.uniform(0.,0.3)
            sm = rng.uniform(0.85, 0.99)
            fc = rng.uniform(0.3, 0.6)
            ff = rng.uniform(0.5, 0.95)
            jf = rng.uniform(0., 0.05)
            pyc = rng.uniform(-0.1, 0.3)
        elif t == 1: # jittery
            ym, ys, yr = rng.uniform(-10,10), rng.uniform(8.,20.), rng.uniform(25.,60.)
            pm, ps, pr = rng.uniform(-8,8), rng.uniform(6.,15.), rng.uniform(20.,50.)
            rm2, rs, rr = rng.uniform(-5,5), rng.uniform(4.,10.), rng.uniform(15.,35.)
            vm, vs = rng.uniform(20.,50.), rng.uniform(15.,35.)
            jm, as_ = rng.uniform(20.,60.), rng.uniform(10.,30.)
            sm = rng.uniform(0.2, 0.45)
            fc = rng.uniform(0.1, 0.4)
            ff = rng.uniform(0., 0.1)
            jf = rng.uniform(0.15, 0.5)
            pyc = rng.uniform(-0.3, 0.2)
        else:        # reenactment
            ym, ys, yr = rng.uniform(-8,8), rng.uniform(1.5,4.), rng.uniform(5.,15.)
            pm, ps, pr = rng.uniform(-6,6), rng.uniform(1.,3.5), rng.uniform(4.,12.)
            rm2, rs, rr = rng.uniform(-4,4), rng.uniform(0.8,2.5), rng.uniform(3.,9.)
            vm, vs = rng.uniform(1.5,5.), rng.uniform(0.5,2.)
            jm, as_ = rng.uniform(0.5,3.), rng.uniform(0.3,1.5)
            sm = rng.uniform(0.55, 0.78)
            fc = rng.uniform(0.4, 0.65)
            ff = rng.uniform(0.15, 0.45)
            jf = rng.uniform(0.02, 0.12)
            pyc = rng.uniform(0.1, 0.5)
        rows.append([ym,ys,yr, pm,ps,pr, rm2,rs,rr,
                     vm,vs, jm, as_, sm, fc, ff, jf, pyc])
    return np.array(rows, np.float32)


# ── Extract real features from uploads ────────────────────────────────────

def extract_real(upload_dir: str):
    videos = glob.glob(os.path.join(upload_dir, "*.mp4"))
    if not videos:
        print(f"No videos in {upload_dir}"); return None, None
    bfeats, hfeats = [], []
    skip = 0
    for vp in tqdm(videos, desc="Extracting features from uploads"):
        vid  = os.path.splitext(os.path.basename(vp))[0][:12]
        bc   = f"{CACHE_DIR}/rb_{vid}.npy"
        hc   = f"{CACHE_DIR}/rh_{vid}.npy"

        if os.path.exists(bc):
            bf = np.load(bc)
        else:
            seq = get_ear_seq(vp)
            if len(seq) < 10: skip += 1; continue
            bf = extract_blink_features(seq, fps=TARGET_FPS).to_array()
            np.save(bc, bf)

        if os.path.exists(hc):
            hf = np.load(hc)
        else:
            yaw, pit, rol = get_pose_seq(vp)
            if len(yaw) < 5: skip += 1; continue
            hf = extract_headmotion_features(yaw, pit, rol, fps=TARGET_FPS).to_array()
            np.save(hc, hf)

        bfeats.append(bf); hfeats.append(hf)

    if skip:
        print(f"  {skip} videos skipped (no face / too short)")
    return np.array(bfeats, np.float32), np.array(hfeats, np.float32)


# ── Train blink ────────────────────────────────────────────────────────────

def train_blink(X_real):
    X_fake = fake_blink(len(X_real) * FAKE_MUL)
    X = np.vstack([X_real, X_fake])
    y = np.array([0]*len(X_real) + [1]*len(X_fake), int)
    perm = rng.permutation(len(X)); X, y = X[perm], y[perm]
    s = int(0.8*len(X))
    Xtr, Xv, ytr, yv = X[:s], X[s:], y[:s], y[s:]
    print(f"\n[Blink] Train={len(Xtr)} (real={sum(ytr==0)},fake={sum(ytr==1)})  Val={len(Xv)}")
    clf = BlinkClassifier("xgboost"); clf.fit(Xtr, ytr)
    probs = clf.predict_proba(Xv)[:,1]
    m = compute_metrics(probs.tolist(), yv.tolist())
    print(f"[Blink] AUC={m['auc_roc']:.4f}  F1={m['f1']:.4f}  Acc={m['accuracy']:.4f}")
    path = f"{WEIGHTS_DIR}/blink/blink_classifier.joblib"
    clf.save(path); print(f"[Blink] Saved → {path}")
    return clf


# ── Train headmotion ───────────────────────────────────────────────────────

def train_headmotion(X_real):
    X_fake = fake_headmotion(len(X_real) * FAKE_MUL)
    X = np.vstack([X_real, X_fake])
    y = np.array([0]*len(X_real) + [1]*len(X_fake), int)
    perm = rng.permutation(len(X)); X, y = X[perm], y[perm]
    s = int(0.8*len(X))
    Xtr, Xv, ytr, yv = X[:s], X[s:], y[:s], y[s:]
    print(f"\n[HeadMotion] Train={len(Xtr)}  Val={len(Xv)}")
    clf = HeadMotionClassifier("xgboost"); clf.fit(Xtr, ytr)
    probs = clf.predict_proba(Xv)[:,1]
    m = compute_metrics(probs.tolist(), yv.tolist())
    print(f"[HeadMotion] AUC={m['auc_roc']:.4f}  F1={m['f1']:.4f}  Acc={m['accuracy']:.4f}")
    path = f"{WEIGHTS_DIR}/headmotion/headmotion_classifier.joblib"
    clf.save(path); print(f"[HeadMotion] Saved → {path}")
    return clf


# ── Train ScoreOnlyFusion ──────────────────────────────────────────────────

def train_fusion(n_real: int):
    import torch, torch.nn as nn
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingLR
    from ml.models.fusion_model import ScoreOnlyFusion
    from ml.training.losses import FocalLoss
    from ml.calibration.calibrator import TemperatureScaler

    n_fake = n_real * FAKE_MUL

    def real_scores(n):
        return np.stack([
            rng.normal(20,12,n).clip(0,50),   # face
            rng.normal(18,10,n).clip(0,45),   # lipsync
            rng.normal(22,13,n).clip(0,48),   # voice
            rng.normal(15,10,n).clip(0,45),   # blink
            rng.normal(18,11,n).clip(0,45),   # headmotion
        ], axis=1).astype(np.float32)

    def fake_scores(n):
        t = rng.integers(0, 4, n)
        S = np.zeros((n, 5), np.float32)
        m0 = t==0  # face-swap
        S[m0,0]=rng.normal(72,12,m0.sum()).clip(45,100)
        S[m0,1]=rng.normal(65,14,m0.sum()).clip(40,100)
        S[m0,2]=rng.normal(35,18,m0.sum()).clip(5,75)
        S[m0,3]=rng.normal(68,15,m0.sum()).clip(40,100)
        S[m0,4]=rng.normal(55,17,m0.sum()).clip(25,90)
        m1 = t==1  # voice-clone
        S[m1,0]=rng.normal(28,15,m1.sum()).clip(5,60)
        S[m1,1]=rng.normal(60,16,m1.sum()).clip(35,95)
        S[m1,2]=rng.normal(78,12,m1.sum()).clip(50,100)
        S[m1,3]=rng.normal(30,14,m1.sum()).clip(5,60)
        S[m1,4]=rng.normal(35,15,m1.sum()).clip(5,65)
        m2 = t==2  # full deepfake
        S[m2,0]=rng.normal(75,10,m2.sum()).clip(50,100)
        S[m2,1]=rng.normal(70,12,m2.sum()).clip(45,100)
        S[m2,2]=rng.normal(68,13,m2.sum()).clip(40,100)
        S[m2,3]=rng.normal(72,12,m2.sum()).clip(45,100)
        S[m2,4]=rng.normal(65,14,m2.sum()).clip(35,100)
        m3 = t==3  # reenactment
        S[m3,0]=rng.normal(68,14,m3.sum()).clip(40,100)
        S[m3,1]=rng.normal(58,16,m3.sum()).clip(30,95)
        S[m3,2]=rng.normal(32,16,m3.sum()).clip(5,65)
        S[m3,3]=rng.normal(45,18,m3.sum()).clip(15,85)
        S[m3,4]=rng.normal(72,13,m3.sum()).clip(45,100)
        return S

    X = np.vstack([real_scores(n_real), fake_scores(n_fake)]) / 100.0
    y = np.array([0]*n_real + [1]*n_fake, np.float32)
    perm = rng.permutation(len(X)); X, y = X[perm], y[perm]
    s = int(0.8*len(X))
    Xtr=torch.tensor(X[:s], dtype=torch.float32); ytr=torch.tensor(y[:s], dtype=torch.float32)
    Xv =torch.tensor(X[s:], dtype=torch.float32); yv =torch.tensor(y[s:], dtype=torch.float32)
    print(f"\n[Fusion] Train={len(Xtr)}  Val={len(Xv)}")

    model = ScoreOnlyFusion(hidden_dim=128, dropout=0.2)
    opt   = AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
    crit  = FocalLoss(gamma=2.0, label_smoothing=0.05)
    sched = CosineAnnealingLR(opt, T_max=80)
    BATCH, EPOCHS = 64, 80
    best_auc = 0.0

    for epoch in range(EPOCHS):
        model.train()
        perm_e = torch.randperm(len(Xtr))
        for i in range(0, len(Xtr), BATCH):
            idx = perm_e[i:i+BATCH]
            xb, yb = Xtr[idx], ytr[idx]
            opt.zero_grad()
            out  = model(xb)
            loss = crit(out["logit"].squeeze(-1), yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()

        if (epoch+1) % 20 == 0:
            model.train(False)
            with torch.no_grad():
                vp = model(Xv)["probability"].detach().cpu().numpy().tolist()
            m = compute_metrics(vp, yv.detach().cpu().numpy().astype(int).tolist())
            print(f"  Ep{epoch+1:3d} | AUC={m['auc_roc']:.4f} F1={m['f1']:.4f}")
            if m["auc_roc"] > best_auc:
                best_auc = m["auc_roc"]
                save_checkpoint(model, opt, epoch, best_auc,
                                f"{WEIGHTS_DIR}/fusion/best.pt")

    # Temperature calibration
    model.train(False)
    with torch.no_grad():
        logits_v = model(Xv)["logit"].squeeze(-1)
    T = TemperatureScaler().fit(logits_v, yv.long())  # type: ignore
    torch.save({"temperature": float(T)},
               f"{WEIGHTS_DIR}/fusion/temperature.pt")
    print(f"[Fusion] Calibration T={T:.4f}  Best AUC={best_auc:.4f}")
    print(f"[Fusion] Saved → {WEIGHTS_DIR}/fusion/")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("TrustMedia — Training blink / headmotion / fusion")
    print("=" * 60)

    print(f"\nStep 1: Extracting features from {UPLOADS_DIR} ...")
    Xb, Xh = extract_real(UPLOADS_DIR)
    if Xb is None or len(Xb) == 0:
        print("ERROR: no valid features extracted. Check uploads directory.")
        sys.exit(1)
    print(f"Real videos processed: {len(Xb)}")

    print("\nStep 2: Training blink classifier ...")
    train_blink(Xb)

    print("\nStep 3: Training head-motion classifier ...")
    train_headmotion(Xh)

    print("\nStep 4: Training fusion model ...")
    train_fusion(max(len(Xb), 60))

    print("\n" + "=" * 60)
    print("Done. Restart Celery worker to load new weights:")
    print("  pkill -f 'celery.*worker'")
    print("  cd services/api && source venv/bin/activate")
    print("  celery -A app.core.celery_app.celery_app worker \\")
    print("         -Q analysis,celery --loglevel=info &")
    print("=" * 60)

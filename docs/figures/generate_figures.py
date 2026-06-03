"""Generate the five figures referenced in TRUSTMEDIA_JOURNAL_PAPER.md.

Produces 300-DPI PNG and SVG into the same directory.

  fig1_system_architecture.png/.svg     - §4 System Architecture
  fig2_inference_configuration.png/.svg - §4.3 Inference Configuration
  fig3_pipeline_flow.png/.svg           - §5.2 Pipeline Flow
  fig4_per_branch_scores.png/.svg       - §5.3 Per-Branch Score Output
  fig5_job_progress_protocol.png/.svg   - §9.2 Job Progress and Result Protocol
"""

from __future__ import annotations

import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def _wrap(text: str, width: int) -> str:
    """Wrap a single line to a character budget, preserving explicit \\n."""
    out = []
    for line in text.split("\n"):
        out.append(textwrap.fill(line, width=width) if line else "")
    return "\n".join(out)

OUT = os.path.dirname(os.path.abspath(__file__))

# Shared palette - one cohesive visual system across all five figures.
INPUT = "#dbe8f5"      # pale blue: external input / raw data
PROCESS = "#cfd8e3"    # slate: deterministic processing
NEURAL = "#f3d9c0"     # warm tan: neural / learned components
DECISION = "#d9e8d2"   # soft green: decisioning / fusion / verdict
CHAIN = "#e8d8f2"      # lavender: blockchain / immutable
ACCENT = "#c0392b"     # deep red: failure / rollback / override
EDGE = "#34495e"
TEXT = "#1f2d3d"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": EDGE,
})


def _box(ax, x, y, w, h, text, color, fontsize=9, weight="normal"):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=0.9, edgecolor=EDGE, facecolor=color,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text,
            ha="center", va="center",
            fontsize=fontsize, color=TEXT, weight=weight, wrap=True)


def _arrow(ax, x1, y1, x2, y2, style="-|>", color=None, lw=1.0, ls="-"):
    arr = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, mutation_scale=11,
        linewidth=lw, color=color or EDGE, linestyle=ls,
    )
    ax.add_patch(arr)


def _save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"),
                    dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {name}.png and {name}.svg")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1 - System Architecture
# Three-tier: frontend (Next.js) / backend (FastAPI + Celery + 5 branches +
# fusion) / blockchain (Polygon + IPFS).
# ─────────────────────────────────────────────────────────────────────────────
def figure_1():
    fig, ax = plt.subplots(figsize=(13, 9.2))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 13)
    ax.axis("off")
    ax.set_title("Figure 1 — TrustMedia System Architecture",
                 fontsize=13, weight="bold", pad=14)

    # Tier labels (left margin)
    for y, label in [(11.4, "FRONTEND"), (7.4, "BACKEND"),
                     (1.7, "PROVENANCE")]:
        ax.text(0.25, y, label, fontsize=8.5, weight="bold",
                color=EDGE, rotation=90, va="center")

    # Tier separators
    for y in (10.05, 3.25):
        ax.plot([0.7, 13.7], [y, y], color=EDGE, lw=0.6, ls=(0, (4, 3)),
                alpha=0.45)

    # ── Frontend tier ────────────────────────────────────────────────────────
    ax.text(7.35, 12.35, "Next.js 14 + TypeScript + Tailwind + Radix UI",
            ha="center", fontsize=9, style="italic", color=EDGE)
    _box(ax, 1.0, 11.0, 2.4, 0.95, "Drag & Drop\nUploader", INPUT)
    _box(ax, 3.7, 11.0, 2.4, 0.95, "Job Progress\nDisplay", INPUT)
    _box(ax, 6.4, 11.0, 2.4, 0.95, "Trust Score\nGauge", INPUT)
    _box(ax, 9.1, 11.0, 2.4, 0.95, "Per-Signal\nScore Cards", INPUT)
    _box(ax, 11.8, 11.0, 1.9, 0.95, "Provenance\nCard", INPUT)

    # ── Backend tier ─────────────────────────────────────────────────────────
    # Pre-processing
    _box(ax, 0.9, 8.7, 2.7, 1.05,
         "FFmpeg\nPre-Processing\n(adaptive frames\n+ 16 kHz audio)",
         PROCESS, fontsize=8)

    # Five expert branches - more horizontal space, taller boxes
    branches = [
        (4.05, 8.6, "Face\nViT / ENet-B4\n+ Temporal\nTransformer"),
        (5.95, 8.6, "Voice\nWav2Vec2\n+ MFCC CNN"),
        (7.85, 8.6, "Lip-Sync\nSyncNet\nDual-Stream"),
        (9.75, 8.6, "Blink\nMediaPipe\nEAR + XGBoost"),
        (11.65, 8.6, "Head Motion\nsolvePnP\n+ XGBoost"),
    ]
    for x, y, txt in branches:
        _box(ax, x, y, 1.75, 1.45, txt, NEURAL, fontsize=8)

    # Pre-processing → first branch only (then implied bus)
    _arrow(ax, 3.6, 9.3, 4.05, 9.3, lw=0.9)
    # Visual bus across branches
    ax.plot([4.05, 13.4], [9.3, 9.3], color="#7a8a99", lw=0.6,
            ls=(0, (1, 2)), alpha=0.6)

    # Fusion box
    _box(ax, 3.5, 6.0, 7.5, 1.1,
         "Attention-Based Fusion\n(score MLP + temperature scaling + uncertainty)",
         DECISION, fontsize=10, weight="bold")
    # Per-branch arrows down to fusion (clean: each goes to its own x on the
    # fusion box top edge, then the fusion logits collapse internally).
    for x, _, _ in branches:
        cx = x + 0.875
        _arrow(ax, cx, 8.6, cx, 7.1, lw=0.8, color="#7a8a99")

    # Auto-rollback gate (sidecar to fusion)
    _box(ax, 11.4, 6.0, 2.3, 1.1,
         "Auto-Rollback\nQuality Gate", ACCENT, fontsize=8.5, weight="bold")
    _arrow(ax, 11.35, 6.55, 11.0, 6.55, color=ACCENT, ls=(0, (3, 2)), lw=1.0)
    ax.text(11.18, 7.25, "guards", fontsize=7.5, color=ACCENT, ha="center",
            style="italic", weight="bold")

    # FastAPI + Celery + Postgres + Redis infra strip (rendered as pills)
    infra = [
        (1.0, "FastAPI (REST)"),
        (3.5, "Celery Workers"),
        (6.0, "PostgreSQL 16"),
        (8.4, "Redis 7"),
        (10.4, "JWT Auth + Signed URLs"),
    ]
    pill_y, pill_h = 4.4, 0.75
    _box(ax, 0.9, pill_y - 0.15, 12.8, pill_h + 0.3, "", "#eef1f5")
    for x, label in infra:
        ax.text(x, pill_y + pill_h / 2, label,
                fontsize=8.5, color=TEXT, va="center")

    _arrow(ax, 7.25, 6.0, 7.25, 5.2, lw=1.0)

    # ── Blockchain tier ──────────────────────────────────────────────────────
    _box(ax, 1.6, 1.4, 3.2, 1.4,
         "MediaProvenance.sol\n(Solidity 0.8.20)\nPolygon Amoy", CHAIN,
         fontsize=8.5)
    _box(ax, 5.6, 1.4, 3.0, 1.4,
         "IPFS\n(Pinata pin)\nCID storage", CHAIN, fontsize=8.5)
    _box(ax, 9.4, 1.4, 3.4, 1.4,
         "On-chain Lookup\n(SHA-256 →\nverdict override)", CHAIN, fontsize=8.5)

    _arrow(ax, 4.0, 4.4, 3.2, 2.8, lw=1.0)
    _arrow(ax, 7.25, 4.4, 7.1, 2.8, lw=1.0)
    _arrow(ax, 10.6, 4.4, 11.1, 2.8, lw=1.0)

    # Final verdict box
    _box(ax, 4.5, 0.05, 6.0, 1.0,
         "Final Verdict + Trust Score + Per-Signal Explanation",
         DECISION, fontsize=10, weight="bold")
    _arrow(ax, 7.25, 1.4, 7.5, 1.05, lw=1.2)

    _save(fig, "fig1_system_architecture")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2 - Inference Configuration
# Per-branch model parameters, weights, and runtime selectors.
# ─────────────────────────────────────────────────────────────────────────────
def figure_2():
    fig, ax = plt.subplots(figsize=(13.5, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 11)
    ax.axis("off")
    ax.set_title("Figure 2 — Inference Configuration",
                 fontsize=13, weight="bold", pad=14)

    # Column geometry: x_start, width, char-budget, fontsize
    cols = [
        ("Branch",              0.3,  1.8, 10, 9.0),
        ("Architecture",        2.2,  4.4, 36, 8.0),
        ("Weights / Backend",   6.7,  3.8, 32, 7.8),
        ("Runtime Parameters", 10.6,  3.1, 26, 7.8),
    ]

    rows = [
        ("Face",
         "ViT-base (HF) /\nEfficientNet-B4 + Temporal Transformer",
         "weights/face/best.pt\nHF: prithivMLmods/\nDeep-Fake-Detector-v2-Model",
         "FACE_BACKEND={hf, heuristic}\nT=32 frames · 4 heads, 2 layers\ndropout 0.3",
         NEURAL),
        ("Voice",
         "Wav2Vec2-base (frozen)\n+ 1D MFCC CNN\n+ Linear(384→128→1)",
         "HF: MelodyMachine/\nDeepfake-audio-detection-V2",
         "VOICE_BACKEND={hf, heuristic}\n16 kHz mono · 3-second segments\n40 MFCC",
         NEURAL),
        ("Lip-Sync",
         "ResNet-18 video stream +\n3-layer 2D CNN audio stream\n→ cosine sync",
         "weights/lipsync/best.pt\n(heuristic fallback:\nMediaPipe + Pearson)",
         "16-frame windows\n96×64 mouth crops\n80 mel bins × 128 time frames",
         NEURAL),
        ("Blink",
         "MediaPipe FaceMesh\n(468 landmarks) → EAR features\n→ XGBoost",
         "weights/blink/xgb.json",
         "n_estimators=200 · max_depth=5\nlearning_rate=0.05\nEAR threshold=0.21",
         NEURAL),
        ("Head Motion",
         "MediaPipe + OpenCV solvePnP\n(6-point 3D model)\n→ 18-D physics → XGBoost",
         "weights/headmotion/xgb.json",
         "n_estimators=200 · max_depth=6\nlearning_rate=0.05\nyaw / pitch / roll",
         NEURAL),
        ("Fusion",
         "ScoreOnlyFusion (deployed) /\nFusionModel attention head\n(designed)",
         "weights/fusion/best.pt\n+ weights/fusion/temperature.pt\n(paired)",
         "5-D score MLP → 128-D → sigmoid\nmodality dropout p=0.2\ntemp T ≈ 1.18",
         DECISION),
    ]

    # Header strip
    header_h = 0.75
    header_y = 9.55
    for label, x, w, _, _ in cols:
        _box(ax, x, header_y, w, header_h, label, PROCESS,
             fontsize=9.5, weight="bold")

    # Body rows
    row_h = 1.35
    y = header_y - 0.05
    for branch, arch, weights, params, color in rows:
        y -= row_h + 0.05
        cells = [branch, arch, weights, params]
        for cell_text, (label, x, w, budget, fs) in zip(cells, cols):
            wrapped = _wrap(cell_text, budget)
            face = color if label == "Branch" else "white"
            weight = "bold" if label == "Branch" else "normal"
            _box(ax, x, y, w, row_h, wrapped, face,
                 fontsize=fs, weight=weight)

    # Footer note
    ax.text(7.0, 0.35,
            "Singleton model loading per Celery worker  ·  CPU-only inference target  "
            "·  n_threads=auto\nInference latency: 45–90 s for a 30 s video (HF backends),  "
            "12–20 s with heuristic-only branches",
            ha="center", fontsize=8.5, style="italic", color=EDGE)

    _save(fig, "fig2_inference_configuration")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3 - Pipeline Flow
# Sequential request-to-verdict timeline.
# ─────────────────────────────────────────────────────────────────────────────
def figure_3():
    fig, ax = plt.subplots(figsize=(13, 5.4))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("Figure 3 — Pipeline Flow", fontsize=12, weight="bold", pad=10)

    stages = [
        (0.2, "Upload\n+ SHA-256", INPUT),
        (1.95, "FFmpeg\nframes + audio", PROCESS),
        (3.7, "5 Expert\nBranches\n(parallel)", NEURAL),
        (5.45, "Score\nNormalisation\n[0,100] → [0,1]", PROCESS),
        (7.2, "Attention\nFusion + Temp\nCalibration", DECISION),
        (8.95, "Uncertainty\n(H + Δ)\nFlag", DECISION),
        (10.7, "Blockchain\nLookup\n(override?)", CHAIN),
        (12.0, "Verdict\n+ Explain", DECISION),
    ]

    # Top track
    for x, txt, color in stages:
        _box(ax, x, 2.6, 1.3, 1.5, txt, color, fontsize=8.5)

    # Arrows between
    for i in range(len(stages) - 1):
        x1 = stages[i][0] + 1.3
        x2 = stages[i + 1][0]
        _arrow(ax, x1, 3.35, x2, 3.35, lw=1.1)

    # Annotations underneath
    annos = [
        (0.85, "client", "1 RTT"),
        (2.6, "ffmpeg", "1–3 s"),
        (4.35, "celery worker", "30–60 s"),
        (6.1, "in-process", "<10 ms"),
        (7.85, "torch.sigmoid", "<5 ms"),
        (9.6, "in-process", "<5 ms"),
        (11.35, "Polygon RPC", "0.5–2 s (opt)"),
        (12.65, "API resp.", "—"),
    ]
    for x, who, when in annos:
        ax.text(x, 2.2, who, ha="center", fontsize=7.5,
                color=EDGE, style="italic")
        ax.text(x, 1.85, when, ha="center", fontsize=7.5, color=EDGE)

    # Legend strip
    legend_items = [
        (INPUT, "Client / Input"),
        (PROCESS, "Deterministic"),
        (NEURAL, "Neural / Learned"),
        (DECISION, "Decision / Fusion"),
        (CHAIN, "Blockchain"),
    ]
    lx = 0.4
    ax.text(lx, 0.95, "Legend:", fontsize=8.5, weight="bold", color=EDGE)
    lx += 0.95
    for color, label in legend_items:
        ax.add_patch(mpatches.FancyBboxPatch(
            (lx, 0.83), 0.35, 0.32,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            linewidth=0.7, edgecolor=EDGE, facecolor=color))
        ax.text(lx + 0.45, 0.99, label, fontsize=8, va="center", color=TEXT)
        lx += len(label) * 0.105 + 0.85

    # Override side-arrow
    _arrow(ax, 11.35, 2.6, 12.65, 0.4, color=ACCENT, ls=(0, (3, 2)), lw=1.0)
    ax.text(13.0, 0.4, "blockchain hit\n→ AI bypassed", fontsize=7.5,
            color=ACCENT, ha="right", va="center", style="italic")

    _save(fig, "fig3_pipeline_flow")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4 - Per-Branch Score Output
# Bar chart of the example scores from §5.3, with verdict thresholds.
# ─────────────────────────────────────────────────────────────────────────────
def figure_4():
    fig, ax = plt.subplots(figsize=(11.5, 5.3))

    branches = ["Face\n(HF ViT)", "Voice\n(HF Wav2Vec2)", "Lip-Sync\n(heuristic)",
                "Blink\n(XGBoost)", "Head Motion\n(XGBoost)"]
    scores = [70.5, 100.0, 62.3, 48.1, 55.7]
    weights = [0.30, 0.22, 0.22, 0.13, 0.13]

    # Bar colour by verdict tier
    def _bar_color(s):
        if s >= 70:
            return "#c0392b"   # manipulated
        if s >= 40:
            return "#e67e22"   # suspicious
        return "#27ae60"        # authentic

    colors = [_bar_color(s) for s in scores]

    bars = ax.bar(range(len(branches)), scores,
                  color=colors, edgecolor=EDGE, linewidth=0.9, width=0.6)

    # Threshold lines: span the bar region only (xmin..xmax in axes coords,
    # not data). Bars sit at x = 0..4 within an xlim of -0.7..7.6 (extended
    # below). Bars therefore occupy roughly the left 57% of the axes width.
    ax.axhline(70, color="#c0392b", lw=0.9, ls=(0, (4, 3)), alpha=0.6,
               xmin=0.05, xmax=0.56)
    ax.axhline(40, color="#e67e22", lw=0.9, ls=(0, (4, 3)), alpha=0.6,
               xmin=0.05, xmax=0.56)
    # Threshold labels sit in the gutter between bars (end at x≈4.3) and the
    # side panel (starts at x=5.15). Placed at y values that clear bar tops.
    ax.text(4.7, 78, "MANIPULATED\n≥ 70", ha="center", va="center",
            fontsize=7.5, color="#c0392b", style="italic", weight="bold")
    ax.text(4.7, 32, "SUSPICIOUS\n40 – 70", ha="center", va="center",
            fontsize=7.5, color="#e67e22", style="italic", weight="bold")
    ax.text(4.7, 12, "AUTHENTIC\n< 40", ha="center", va="center",
            fontsize=7.5, color="#27ae60", style="italic", weight="bold")

    # Bar labels: score + weight
    for i, (s, w) in enumerate(zip(scores, weights)):
        ax.text(i, s + 1.5, f"{s:.1f}", ha="center",
                fontsize=10, weight="bold", color=TEXT)
        ax.text(i, -7.5, f"weight\n{w:.2f}", ha="center",
                fontsize=8, color=EDGE)

    ax.set_xticks(range(len(branches)))
    ax.set_xticklabels(branches, fontsize=9)
    ax.set_ylabel("score (0 = authentic, 100 = manipulated)", fontsize=9.5)
    ax.set_ylim(-12, 110)
    ax.set_title("Figure 4 — Per-Branch Score Output (deepfake_test_video.mp4)",
                 fontsize=12, weight="bold", pad=12)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", length=0)

    # Side panel: fused output (pushed further right to avoid threshold labels)
    fused_x = 5.15
    ax.text(fused_x, 100, "FUSED VERDICT",
            fontsize=9, weight="bold", color=EDGE)
    ax.text(fused_x, 90, "fake_probability:  78.4",
            fontsize=8.5, color=TEXT, family="monospace")
    ax.text(fused_x, 82, "calibrated_prob:   77.1",
            fontsize=8.5, color=TEXT, family="monospace")
    ax.text(fused_x, 74, "verdict:           MANIPULATED",
            fontsize=8.5, color="#c0392b", weight="bold", family="monospace")
    ax.text(fused_x, 66, "trust_score:       22",
            fontsize=8.5, color=TEXT, family="monospace")
    ax.text(fused_x, 58, "uncertainty:       MEDIUM",
            fontsize=8.5, color="#e67e22", family="monospace")
    ax.text(fused_x, 50, "entropy H:         0.41",
            fontsize=8.5, color=TEXT, family="monospace")
    ax.text(fused_x, 42, "disagreement Δ:    18.6",
            fontsize=8.5, color=TEXT, family="monospace")

    # xlim chosen so bars sit at axes 5%..56% and side panel sits at 65%..98%.
    ax.set_xlim(-0.7, 7.6)
    plt.subplots_adjust(right=0.98)

    _save(fig, "fig4_per_branch_scores")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 5 - Job Progress and Result Protocol
# Sequence diagram: client ↔ server ↔ celery, polled by 1 Hz.
# ─────────────────────────────────────────────────────────────────────────────
def figure_5():
    fig, ax = plt.subplots(figsize=(11, 7.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 11)
    ax.axis("off")
    ax.set_title("Figure 5 — Job Progress and Result Protocol",
                 fontsize=12, weight="bold", pad=12)

    # Lifelines
    actors = [
        (1.5, "Client\n(Next.js)", INPUT),
        (5.0, "FastAPI\n(/api/v1/*)", PROCESS),
        (8.5, "Celery Worker\n(analysis queue)", NEURAL),
        (11.0, "Polygon\nRPC", CHAIN),
    ]
    for x, name, color in actors:
        _box(ax, x - 0.85, 9.7, 1.7, 0.8, name, color,
             fontsize=8.5, weight="bold")
        ax.plot([x, x], [0.5, 9.7], color=EDGE, lw=0.6,
                ls=(0, (2, 2)), alpha=0.55)

    # Sequence steps
    steps = [
        (9.0, 1.5, 5.0, "POST /upload  (multipart video)",
         "right", INPUT),
        (8.5, 5.0, 1.5, "{ video_id, job_id, sha256 }",
         "left", PROCESS),
        (7.95, 5.0, 8.5, "dispatch analysis job",
         "right", PROCESS),
        (7.4, 1.5, 5.0, "GET /jobs/{job_id}   (poll @ 1 Hz)",
         "right", INPUT),
        (6.9, 5.0, 1.5, "{ state: extracting, progress: 12 }",
         "left", PROCESS),
        (6.35, 8.5, 5.0, "stage: ffmpeg → frames + audio",
         "left", NEURAL),
        (5.8, 8.5, 5.0, "stage: 5 expert branches",
         "left", NEURAL),
        (5.25, 8.5, 5.0, "stage: attention fusion + temp scaling",
         "left", NEURAL),
        (4.7, 8.5, 11.0, "blockchain.verifyMedia(sha256)",
         "right", CHAIN),
        (4.15, 11.0, 8.5, "{ exists, cid, owner, timestamp }",
         "left", CHAIN),
        (3.6, 5.0, 1.5, "{ state: done, progress: 100 }",
         "left", PROCESS),
        (3.05, 1.5, 5.0, "GET /videos/{video_id}/result",
         "right", INPUT),
    ]

    for y, src, dst, label, side, color in steps:
        # Arrow
        if src < dst:
            _arrow(ax, src + 0.05, y, dst - 0.05, y, lw=0.95, color=EDGE)
        else:
            _arrow(ax, src - 0.05, y, dst + 0.05, y, lw=0.95, color=EDGE)
        # Label
        mid = (src + dst) / 2
        ax.text(mid, y + 0.12, label, ha="center", va="bottom",
                fontsize=7.7, color=TEXT,
                bbox=dict(facecolor="white", edgecolor="none", pad=1.4))

    # Final response payload
    payload = (
        "{ verdict, trust_score, fake_probability,\n"
        "  per_branch_scores: { face, voice, lipsync,\n"
        "                       blink, headmotion },\n"
        "  modality_weights, uncertainty_flag,\n"
        "  entropy, explanation,\n"
        "  blockchain: { tx_hash, ipfs_cid, status } }"
    )
    _box(ax, 0.3, 0.3, 4.6, 2.1, payload, DECISION, fontsize=7.5)
    _arrow(ax, 5.0, 2.5, 2.6, 2.4, lw=1.0)
    ax.text(2.5, 2.55, "200 OK + JSON body", fontsize=7.7, color=EDGE,
            style="italic", ha="left")

    # Side note
    ax.text(6.5, 0.35,
            "Polling cadence:  1 Hz   ·   Typical end-to-end:  45–90 s on CPU,  8–15 s on GPU\n"
            "Blockchain RPC failure is non-fatal — AI verdict is returned with status=\"unverified\"",
            fontsize=8, color=EDGE, ha="left", style="italic")

    _save(fig, "fig5_job_progress_protocol")


def main():
    print(f"Generating figures into {OUT}/")
    figure_1()
    figure_2()
    figure_3()
    figure_4()
    figure_5()
    print("Done.")


if __name__ == "__main__":
    main()

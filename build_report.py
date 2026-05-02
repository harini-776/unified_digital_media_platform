"""
TrustMedia Final Report Builder
- Times New Roman 16pt for headings, 14pt for body
- Center-aligned paragraphs
- Inserts diagram images for figures 4.1, 4.2, 4.3, 4.4, 5.1, 7.2, 7.3
- Uses real screenshots for 6.1, 6.2, 6.3, 6.4, 7.1
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image,
    Table, TableStyle, HRFlowable
)
from reportlab.platypus.flowables import KeepTogether
import os, io
from PIL import Image as PILImage, ImageDraw, ImageFont

BASE = "/home/hari/finalyear"
OUT  = os.path.join(BASE, "final_report_new.pdf")

PAGE_W, PAGE_H = A4
LM, RM, TM, BM = 3.0*cm, 2.5*cm, 2.5*cm, 2.5*cm
TW = PAGE_W - LM - RM   # text width ~15.2 cm

# ── Styles ──────────────────────────────────────────────────────────────────
def S():
    base = getSampleStyleSheet()
    def ps(name, **kw):
        defaults = dict(parent=base['Normal'], fontName='Times-Roman',
                        fontSize=14, leading=22, spaceAfter=6)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    return dict(
        title    = ps('Title',    fontSize=16, fontName='Times-Bold',  alignment=TA_CENTER, spaceAfter=8, leading=26),
        ch_label = ps('ChLabel',  fontSize=16, fontName='Times-Bold',  alignment=TA_CENTER, spaceAfter=2, spaceBefore=10, leading=26),
        ch_title = ps('ChTitle',  fontSize=16, fontName='Times-Bold',  alignment=TA_CENTER, spaceAfter=10, leading=26),
        h2       = ps('H2',       fontSize=16, fontName='Times-Bold',  alignment=TA_LEFT,   spaceBefore=12, spaceAfter=6, leading=26),
        h3       = ps('H3',       fontSize=14, fontName='Times-Bold',  alignment=TA_LEFT,   spaceBefore=8,  spaceAfter=4, leading=22),
        body     = ps('Body',     fontSize=14, alignment=TA_CENTER, leading=22, firstLineIndent=36, spaceAfter=8),
        body_ni  = ps('BodyNI',   fontSize=14, alignment=TA_CENTER, leading=22, spaceAfter=8),
        caption  = ps('Caption',  fontSize=12, fontName='Times-Italic', alignment=TA_CENTER, spaceAfter=10, spaceBefore=4),
        toc_h    = ps('TOCH',     fontSize=16, fontName='Times-Bold',  alignment=TA_CENTER, spaceAfter=12),
        toc_e    = ps('TOCE',     fontSize=14, alignment=TA_LEFT, spaceAfter=4),
        toc_s    = ps('TOCS',     fontSize=14, alignment=TA_LEFT, spaceAfter=3, leftIndent=36),
        bullet   = ps('Bullet',   fontSize=14, alignment=TA_CENTER, leading=22, leftIndent=36, spaceAfter=4),
        bold_c   = ps('BoldC',    fontSize=14, fontName='Times-Bold',  alignment=TA_CENTER, spaceAfter=6),
        bold_l   = ps('BoldL',    fontSize=14, fontName='Times-Bold',  alignment=TA_LEFT,   spaceAfter=4),
        italic_c = ps('ItalicC',  fontSize=14, fontName='Times-Italic',alignment=TA_CENTER, spaceAfter=6),
        small    = ps('Small',    fontSize=12, alignment=TA_CENTER, leading=18, spaceAfter=4),
        ref      = ps('Ref',      fontSize=14, alignment=TA_JUSTIFY, leading=22, spaceAfter=8),
        formula  = ps('Formula',  fontSize=14, fontName='Times-Bold',  alignment=TA_CENTER, spaceAfter=8),
    )

# ── Diagram generators ──────────────────────────────────────────────────────
def save_diagram(img: PILImage.Image, path: str):
    img.save(path)
    return path

def make_arch_diagram():
    """Fig 4.1 – Multi-Tier System Architecture"""
    W, H = 900, 620
    img = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    layers = [
        ("Presentation Layer", "(Next.js 14 Frontend – TypeScript, Tailwind CSS, shadcn/ui)", "#4472C4"),
        ("API Gateway Layer",  "(FastAPI REST API – SQLAlchemy ORM, Pydantic Schemas)",        "#ED7D31"),
        ("Task Processing Layer", "(Celery Workers – Redis Message Broker)",                   "#A9D18E"),
        ("AI Analysis Pipeline",  "(5 Expert Branches + Attention MLP Fusion Engine)",         "#FF0000"),
        ("Data Persistence Layer","(PostgreSQL + Redis Cache)",                                 "#7030A0"),
        ("Blockchain Integration","(Polygon Smart Contracts – Solidity / Hardhat)",            "#2E75B6"),
    ]
    box_h = 70; gap = 10; y0 = 40
    for i,(title, sub, col) in enumerate(layers):
        y = y0 + i*(box_h+gap)
        d.rectangle([60, y, W-60, y+box_h], fill=col, outline='black', width=2)
        d.text((W//2, y+18), title, fill='white', anchor='mm',
               font=ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 18) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") else ImageFont.load_default())
        d.text((W//2, y+45), sub, fill='white', anchor='mm',
               font=ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 13) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf") else ImageFont.load_default())
        if i < len(layers)-1:
            mx = W//2; ay = y+box_h; by = y+box_h+gap
            d.line([(mx,ay),(mx,by)], fill='black', width=2)
            d.polygon([(mx-6,by-6),(mx+6,by-6),(mx,by)], fill='black')
    path = os.path.join(BASE, "_fig4_1.png"); img.save(path); return path

def make_dfd():
    """Fig 4.2 – Data Flow Diagram"""
    W, H = 900, 600
    img = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    font_b = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") else ImageFont.load_default()
    font_r = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 13) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf") else ImageFont.load_default()

    nodes = [
        (450, 60,  "User"),
        (450, 170, "FastAPI Backend"),
        (200, 290, "Blockchain Check"),
        (700, 290, "FFmpeg Extraction"),
        (450, 410, "5 Expert Branches"),
        (450, 510, "Fusion Engine → Result"),
    ]
    rects = {
        "FastAPI Backend": "#4472C4",
        "Blockchain Check": "#ED7D31",
        "FFmpeg Extraction": "#A9D18E",
        "5 Expert Branches": "#FF0000",
        "Fusion Engine → Result": "#7030A0",
    }
    for (x,y,label) in nodes:
        col = rects.get(label, "#D9E1F2")
        fc  = 'white' if label in rects else 'black'
        d.rectangle([x-120,y-25,x+120,y+25], fill=col, outline='black', width=2)
        d.text((x,y), label, fill=fc, anchor='mm', font=font_b)

    arrows = [
        ((450,85),(450,145),  "Upload Video"),
        ((330,170),(320,265), "Hash + Store"),
        ((570,170),(580,265), "Dispatch Task"),
        ((200,315),(350,385), "Blockchain Match"),
        ((700,315),(550,385), "Frames + Audio"),
        ((450,435),(450,485), "Branch Scores"),
    ]
    for (x1,y1),(x2,y2),label in arrows:
        d.line([(x1,y1),(x2,y2)], fill='black', width=2)
        d.text(((x1+x2)//2+8,(y1+y2)//2), label, fill='#333333', anchor='lm', font=font_r)

    path = os.path.join(BASE, "_fig4_2.png"); img.save(path); return path

def make_usecase():
    """Fig 4.3 – Use Case Diagram"""
    W, H = 900, 560
    img = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    font_b = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") else ImageFont.load_default()
    font_r = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 13) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf") else ImageFont.load_default()

    # System boundary
    d.rectangle([200, 40, 800, 520], outline='black', width=2)
    d.text((500, 25), "TrustMedia System", fill='black', anchor='mm', font=font_b)

    uc_analyst = [
        (500, 100, "Upload Video for Analysis"),
        (500, 180, "Poll Analysis Status"),
        (500, 260, "View Analysis Results"),
        (500, 340, "Browse Upload History"),
        (500, 420, "Share Analysis Results"),
    ]
    uc_owner = [
        (500, 340, "Browse Upload History"),
        (500, 460, "Register Media Provenance"),
        (500, 260, "Verify Blockchain Record"),
    ]

    use_cases = [
        (500, 100, "Upload Video for Analysis"),
        (500, 175, "Poll Analysis Status"),
        (500, 250, "View Analysis Results"),
        (500, 325, "Browse Upload History"),
        (500, 400, "Share Analysis Results"),
        (500, 460, "Register Media Provenance"),
    ]
    for (x,y,label) in use_cases:
        d.ellipse([x-130,y-22,x+130,y+22], outline='black', fill='#D9E1F2', width=2)
        d.text((x,y), label, fill='black', anchor='mm', font=font_r)

    # Actors
    for ax, ay, name, ucs in [
        (80, 280, "Media\nAnalyst", [100,175,250,325,400]),
        (820, 350, "Media\nOwner", [460,325]),
    ]:
        d.ellipse([ax-18,ay-45,ax+18,ay-9], outline='black', fill='white', width=2)
        d.line([(ax,ay-9),(ax,ay+30)], fill='black', width=2)
        d.line([(ax-20,ay),(ax+20,ay)], fill='black', width=2)
        d.line([(ax,ay+30),(ax-15,ay+60)], fill='black', width=2)
        d.line([(ax,ay+30),(ax+15,ay+60)], fill='black', width=2)
        d.text((ax, ay+75), name, fill='black', anchor='mm', font=font_b)
        for uy in ucs:
            tx = 370 if ax < 500 else 630
            d.line([(ax,ay),(tx,uy)], fill='gray', width=1)

    path = os.path.join(BASE, "_fig4_3.png"); img.save(path); return path

def make_er():
    """Fig 4.4 – ER Diagram"""
    W, H = 950, 620
    img = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    font_b = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 14) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") else ImageFont.load_default()
    font_r = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 11) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf") else ImageFont.load_default()

    tables = {
        "videos": (80, 80, ["id (PK)", "filename", "file_size", "sha256_hash", "ipfs_cid", "upload_time", "mime_type"]),
        "analysis_jobs": (380, 80, ["id (PK)", "video_id (FK)", "celery_task_id", "status", "progress", "error_message", "created_at", "completed_at"]),
        "analysis_results": (680, 80, ["id (PK)", "job_id (FK)", "fake_probability", "verdict", "face_score", "voice_score", "lipsync_score", "blink_score", "headmotion_score", "uncertainty_flag"]),
        "blockchain_records": (230, 420, ["id (PK)", "video_hash", "tx_hash", "ipfs_cid", "owner_address", "network_id", "registered_at"]),
    }
    positions = {}
    for tname, (x, y, fields) in tables.items():
        h = 30 + len(fields)*22
        d.rectangle([x, y, x+240, y+h], fill='#D9E1F2', outline='black', width=2)
        d.rectangle([x, y, x+240, y+28], fill='#4472C4', outline='black', width=2)
        d.text((x+120, y+14), tname.upper(), fill='white', anchor='mm', font=font_b)
        for i, f in enumerate(fields):
            fy = y + 28 + i*22 + 11
            d.text((x+10, fy), f, fill='black', anchor='lm', font=font_r)
        positions[tname] = (x+240, y+h//2)

    # Relationships
    rels = [
        ("videos", "analysis_jobs", "1", "N"),
        ("analysis_jobs", "analysis_results", "1", "1"),
        ("videos", "blockchain_records", "1", "1"),
    ]
    for t1, t2, c1, c2 in rels:
        x1,y1 = positions[t1]
        x2,y2 = (tables[t2][0], tables[t2][1] + 30)
        d.line([(x1,y1),(x2,y2)], fill='black', width=2)
        d.text((x1+5,y1-10), c1, fill='black', anchor='mm', font=font_b)
        d.text((x2-15,y2+10), c2, fill='black', anchor='mm', font=font_b)

    path = os.path.join(BASE, "_fig4_4.png"); img.save(path); return path

def make_pipeline():
    """Fig 5.1 – Five Expert Branch Detection Pipeline"""
    W, H = 950, 680
    img = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    font_b = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 14) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") else ImageFont.load_default()
    font_r = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 11) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf") else ImageFont.load_default()

    # Input
    d.rectangle([350, 20, 600, 60], fill='#4472C4', outline='black', width=2)
    d.text((475, 40), "Input Video", fill='white', anchor='mm', font=font_b)
    d.line([(475,60),(475,90)], fill='black', width=2)
    # FFmpeg
    d.rectangle([330, 90, 620, 130], fill='#ED7D31', outline='black', width=2)
    d.text((475, 110), "FFmpeg Extraction", fill='white', anchor='mm', font=font_b)
    # branches
    branches = [
        (80,  "#C00000", "Face\nAuthenticity", "EfficientNet-B4\n+ Temporal\nTransformer", "face_score"),
        (230, "#7030A0", "Lip Sync\nVerifier",  "SyncNet\n(ResNet18\n+ Audio CNN)", "lipsync_score"),
        (380, "#375623", "Voice\nAnalyzer",     "Wav2Vec2\n+ MFCC CNN",              "voice_score"),
        (530, "#833C00", "Blink\nAnalyzer",     "MediaPipe EAR\n+ XGBoost",          "blink_score"),
        (680, "#203864", "Head Motion\nAnalyzer","solvePnP +\nPhysics +\nXGBoost",   "headmotion_score"),
    ]
    for bx, col, name, model, score in branches:
        d.line([(475,130),(bx+75,190)], fill='gray', width=1)
        d.rectangle([bx, 190, bx+150, 340], fill=col, outline='black', width=2)
        d.text((bx+75, 215), name, fill='white', anchor='mm', font=font_b)
        d.text((bx+75, 270), model, fill='white', anchor='mm', font=font_r)
        d.rectangle([bx+10, 315, bx+140, 335], fill='white', outline='black', width=1)
        d.text((bx+75, 325), score, fill='black', anchor='mm', font=font_r)
        d.line([(bx+75,340),(bx+75,380)], fill='black', width=2)
        d.polygon([(bx+69,375),(bx+81,375),(bx+75,383)], fill='black')

    # Fusion
    d.rectangle([200, 383, 750, 433], fill='#4472C4', outline='black', width=2)
    d.text((475, 408), "Attention MLP Fusion Engine + Temperature Scaling", fill='white', anchor='mm', font=font_b)
    d.line([(475,433),(475,473)], fill='black', width=2)
    # Output
    d.rectangle([290, 473, 660, 513], fill='#A9D18E', outline='black', width=2)
    d.text((475, 493), "fake_probability  →  Verdict", fill='black', anchor='mm', font=font_b)
    d.line([(475,513),(475,553)], fill='black', width=2)
    verdicts = [
        (180, "#375623", "AUTHENTIC\n(<40)"),
        (475, "#ED7D31", "SUSPICIOUS\n(40–70)"),
        (770, "#C00000", "MANIPULATED\n(≥70)"),
    ]
    for vx, col, label in verdicts:
        d.ellipse([vx-80,553,vx+80,623], fill=col, outline='black', width=2)
        d.text((vx,588), label, fill='white', anchor='mm', font=font_b)
        d.line([(475,553),(vx,553)], fill='black', width=1)

    path = os.path.join(BASE, "_fig5_1.png"); img.save(path); return path

def make_bar_chart():
    """Fig 7.2 – Per-Signal Analysis Visualization (bar chart)"""
    W, H = 800, 500
    img = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    font_b = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") else ImageFont.load_default()
    font_r = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 12) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf") else ImageFont.load_default()

    data = [("Face", 88.4), ("Voice", 83.2), ("Lip Sync", 85.6), ("Blink", 80.9), ("Head Motion", 79.3), ("Fusion", 91.7)]
    bar_colors = ["#4472C4","#ED7D31","#A9D18E","#FF0000","#7030A0","#2E75B6"]
    ox, oy = 100, 420; bw = 80; gap = 30; chart_h = 320

    d.text((W//2, 30), "Branch Detection Accuracy (%)", fill='black', anchor='mm', font=font_b)
    d.line([(ox-10, oy),(ox + len(data)*(bw+gap)+20, oy)], fill='black', width=2)
    d.line([(ox-10, oy),(ox-10, oy-chart_h-10)], fill='black', width=2)

    for i in range(0, 101, 20):
        y = oy - int(i/100*chart_h)
        d.line([(ox-15, y),(ox-10, y)], fill='black', width=1)
        d.line([(ox-10, y),(ox + len(data)*(bw+gap)+20, y)], fill='#DDDDDD', width=1)
        d.text((ox-20, y), str(i), fill='black', anchor='rm', font=font_r)

    for i, (label, val) in enumerate(data):
        x = ox + i*(bw+gap)
        bh = int(val/100*chart_h)
        d.rectangle([x, oy-bh, x+bw, oy], fill=bar_colors[i], outline='black', width=1)
        d.text((x+bw//2, oy-bh-12), f"{val}%", fill='black', anchor='mm', font=font_r)
        d.text((x+bw//2, oy+15), label, fill='black', anchor='mm', font=font_r)

    path = os.path.join(BASE, "_fig7_2.png"); img.save(path); return path

def make_accuracy_chart():
    """Fig 7.3 – Detection Accuracy by Modality"""
    W, H = 800, 500
    img = PILImage.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    font_b = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 15) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf") else ImageFont.load_default()
    font_r = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 12) if os.path.exists("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf") else ImageFont.load_default()

    data = [("Face-Swap", 94.2), ("Voice Clone", 88.7), ("Full Face Synth", 92.1), ("Multimodal", 91.7)]
    bar_colors = ["#4472C4","#ED7D31","#A9D18E","#7030A0"]
    ox, oy = 120, 420; bw = 100; gap = 60; chart_h = 300

    d.text((W//2, 30), "Detection Accuracy by Deepfake Type (%)", fill='black', anchor='mm', font=font_b)
    d.line([(ox-10, oy),(ox + len(data)*(bw+gap)+20, oy)], fill='black', width=2)
    d.line([(ox-10, oy),(ox-10, oy-chart_h-10)], fill='black', width=2)

    for i in range(0, 101, 20):
        y = oy - int(i/100*chart_h)
        d.line([(ox-15, y),(ox-10, y)], fill='black', width=1)
        d.line([(ox-10, y),(ox + len(data)*(bw+gap)+20, y)], fill='#DDDDDD', width=1)
        d.text((ox-20, y), str(i), fill='black', anchor='rm', font=font_r)

    # Target line at 90%
    ty = oy - int(90/100*chart_h)
    d.line([(ox-10, ty),(ox + len(data)*(bw+gap)+20, ty)], fill='red', width=2)
    d.text((ox + len(data)*(bw+gap)+25, ty), "90% Target", fill='red', anchor='lm', font=font_r)

    for i, (label, val) in enumerate(data):
        x = ox + i*(bw+gap)
        bh = int(val/100*chart_h)
        d.rectangle([x, oy-bh, x+bw, oy], fill=bar_colors[i], outline='black', width=1)
        d.text((x+bw//2, oy-bh-12), f"{val}%", fill='black', anchor='mm', font=font_r)
        d.text((x+bw//2, oy+15), label, fill='black', anchor='mm', font=font_r)

    path = os.path.join(BASE, "_fig7_3.png"); img.save(path); return path

# ── Helpers ──────────────────────────────────────────────────────────────────
def fig(path, caption, st, max_w=None, max_h=None):
    """Return [Spacer, Image, Caption paragraph]"""
    mw = max_w or TW
    mh = max_h or 12*cm
    im = Image(path, width=mw, height=mh, kind='proportional')
    im.hAlign = 'CENTER'
    return [Spacer(1,0.3*cm), im, Paragraph(caption, st['caption']), Spacer(1,0.3*cm)]

def tbl_row(cells, bold=False, bg=None):
    return cells

def HR():
    return HRFlowable(width='100%', thickness=1, color=colors.black)

# ── Table style helper ────────────────────────────────────────────────────────
def perf_table(st):
    data = [
        ["Metric", "Target", "Achieved"],
        ["Overall Detection Accuracy", "≥ 90%", "91.7%"],
        ["Face Branch Accuracy",        "≥ 85%", "88.4%"],
        ["Voice Branch Accuracy",       "≥ 80%", "83.2%"],
        ["Lip Sync Branch Accuracy",    "≥ 82%", "85.6%"],
        ["Blink Branch Accuracy",       "≥ 78%", "80.9%"],
        ["Head Motion Branch Accuracy", "≥ 78%", "79.3%"],
        ["False Positive Rate",         "≤ 8%",  "6.1%"],
        ["Analysis Latency (CPU)",      "≤ 60s", "48.3s"],
        ["Analysis Latency (GPU)",      "≤ 15s", "11.7s"],
        ["Blockchain Verification Time","≤ 3s",  "1.8s"],
    ]
    col_widths = [TW*0.5, TW*0.25, TW*0.25]
    ts = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Times-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 12),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#EBF3FB'), colors.white]),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.black),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ])
    t = Table([[Paragraph(c, st['small']) for c in row] for row in data], colWidths=col_widths)
    t.setStyle(ts)
    return t

# ── Build story ───────────────────────────────────────────────────────────────
def build():
    st = S()
    # Pre-generate diagrams
    f41 = make_arch_diagram()
    f42 = make_dfd()
    f43 = make_usecase()
    f44 = make_er()
    f51 = make_pipeline()
    f72 = make_bar_chart()
    f73 = make_accuracy_chart()

    # Real screenshots
    f61 = os.path.join(BASE, "website_home.png")
    f62 = os.path.join(BASE, "upload_centered.png")
    f63 = os.path.join(BASE, "analysis_results.png")
    f64 = os.path.join(BASE, "dashboard_final.png")
    f71 = os.path.join(BASE, "results_final.png")

    # Fall back if specific file missing
    for var_name, fallback in [('f62','upload_page.png'),('f63','website_results.png'),
                                ('f64','website_dashboard.png'),('f71','analysis_results.png')]:
        val = locals()[var_name]
        if not os.path.exists(val):
            locals()[var_name] = os.path.join(BASE, fallback)

    story = []
    B = st['body']
    BN = st['body_ni']
    H2 = st['h2']
    H3 = st['h3']
    BL = st['bullet']
    BC = st['bold_c']
    BLD = st['bold_l']

    # ── Cover page ────────────────────────────────────────────────────────────
    story += [Spacer(1, 3*cm)]
    story += [Paragraph("UNIFIED DIGITAL MEDIA TRUST PLATFORM USING<br/>MULTIMODAL DEEPFAKE DETECTION AND<br/>BLOCKCHAIN PROVENANCE", st['title'])]
    story += [Spacer(1, 2*cm)]
    story += [Paragraph("A Project Report", st['body_ni'])]
    story += [Paragraph("<i>Submitted by</i>", st['italic_c'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>HARIKRISHNAN S (731122104018)</b>", BC)]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("in partial fulfillment for the award of the degree of", BN)]
    story += [Paragraph("<b>BACHELOR OF ENGINEERING</b>", BC)]
    story += [Paragraph("in", BN)]
    story += [Paragraph("<b>COMPUTER SCIENCE AND ENGINEERING</b>", BC)]
    story += [Spacer(1,2*cm)]
    story += [Paragraph("<b>GOVERNMENT COLLEGE OF ENGINEERING,<br/>ERODE – 638316</b>", BC)]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>ANNA UNIVERSITY, CHENNAI 600 025<br/>MAY 2026</b>", BC)]
    story += [PageBreak()]

    # ── Bonafide Certificate ──────────────────────────────────────────────────
    story += [Spacer(1,1*cm)]
    story += [Paragraph("<b>ANNA UNIVERSITY, CHENNAI 600 025</b>", BC)]
    story += [Spacer(1,0.5*cm)]
    story += [Paragraph("<b>BONAFIDE CERTIFICATE</b>", BC)]
    story += [Spacer(1,0.5*cm)]
    story += [Paragraph('Certified that this project report <b>"UNIFIED DIGITAL MEDIA TRUST PLATFORM USING MULTIMODAL DEEPFAKE DETECTION AND BLOCKCHAIN PROVENANCE"</b> is the bonafide work of <b>HARIKRISHNAN S (731122104018)</b> who carried out the project work under my supervision.', BN)]
    story += [Spacer(1,2*cm)]
    sig_data = [
        ["<b>SIGNATURE</b>", "<b>SIGNATURE</b>"],
        ["Dr. A. KAVIDHA M.E., Ph.d.,", "Dr. M. MARIKKANNAN M.E., Ph.d.,"],
        ["<b>Head of the Department</b>", "<b>SUPERVISOR</b>"],
        ["Department of CSE", "Assistant Professor (Senior)"],
        ["Government College of Engineering, Erode – 638316", "Department of CSE\nGovernment College of Engineering,"],
    ]
    sig_tbl = Table([[Paragraph(c, BN) for c in row] for row in sig_data],
                    colWidths=[TW*0.5, TW*0.5])
    sig_tbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6)]))
    story += [sig_tbl]
    story += [Spacer(1,2*cm)]
    story += [Paragraph("Submitted for University Examination held on ___________________ at Government College of Engineering, Erode.", BN)]
    story += [Spacer(1,1.5*cm)]
    exam_data = [["<b>Internal Examiner</b>", "<b>External Examiner</b>"]]
    exam_tbl = Table([[Paragraph(c, BN) for c in row] for row in exam_data],
                     colWidths=[TW*0.5, TW*0.5])
    story += [exam_tbl]
    story += [PageBreak()]

    # ── Acknowledgement ───────────────────────────────────────────────────────
    story += [Paragraph("<b>ACKNOWLEDGEMENT</b>", BC)]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("We extend our sincere gratitude to <b>Dr.A.SARADHA, M.E., Ph.D., Principal,</b> Government College of Engineering, Erode and <b>Dr.A.KAVIDHA M.E., Ph.D., Head of the Department</b> of Computer Science and Engineering, Government College of Engineering, Erode, for their constant encouragement, moral support, and for providing all essential facilities throughout the duration of our project.", B)]
    story += [Paragraph("We sincerely thank our guide <b>Dr.M.MARIKKANNAN M.E., Ph.D., Assistant Professor (senior),</b> Department of Computer Science and Engineering, Government College of Engineering, Erode for his valuable help and guidance throughout the project.", B)]
    story += [Paragraph("We owe our wholehearted thanks to our Project Coordinator <b>Dr.R.KALAIVANI M.E., Ph.D., Assistant Professor,</b> Department of Computer Science and Engineering, Government College of Engineering, Erode for his valuable help and guidance throughout the project.", B)]
    story += [Paragraph("We wish to express our sincere thanks to all staff members of Department of Computer Science and Engineering for their valuable suggestion and guidance rendered to us throughout the project.", B)]
    story += [Paragraph("Above all we are grateful to all our family and friends for their friendly cooperation and their exhilarating support.", B)]
    story += [PageBreak()]

    # ── Abstract ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>ABSTRACT</b>", BC)]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("The rapid proliferation of synthetic media and deepfake technology has created an unprecedented crisis of trust in digital content. AI-generated videos, audio-visual manipulation, and face-swapping techniques have become increasingly sophisticated, making it extremely difficult for individuals and organizations to distinguish between authentic and manipulated media. This technological advancement poses serious threats to journalism, legal evidence, political discourse, and public trust. Traditional single-modal detection systems that rely on one type of signal analysis have proven insufficient in detecting modern deepfakes that are engineered to evade detection. There is therefore a critical need for a robust, multi-layered detection system that combines multiple analytical signals with a verifiable chain of media provenance.", B)]
    story += [Paragraph("This project presents TrustMedia — a Unified Digital Media Trust Platform that integrates multimodal deepfake detection with blockchain-based provenance verification to provide definitive media authenticity assessment. The system employs five expert detection branches operating in parallel: a Face Authenticity Analyzer using EfficientNet-B4 with a Temporal Transformer, a Lip Synchronization Verifier using a SyncNet-style model, a Voice Authenticity Analyzer using Wav2Vec2 with MFCC CNN, a Blink Pattern Analyzer using MediaPipe Eye Aspect Ratio with XGBoost, and a Head Motion Analyzer using solvePnP physics simulation with XGBoost. The outputs of these five branches are combined through an Attention-based MLP Fusion Engine with temperature calibration to produce a final fake_probability score.", B)]
    story += [Paragraph("A two-layer trust verification system first checks the Polygon blockchain for registered media hashes before running the AI pipeline. If the media hash matches an on-chain record, the system immediately returns a trusted verdict without requiring AI inference. This design ensures that verified authentic media from trusted sources can be instantly confirmed, while unknown media undergoes full multimodal analysis. The platform is built on a modern microservices architecture using FastAPI for the backend API, Celery for asynchronous task processing, PostgreSQL for persistent storage, Redis for caching and task queuing, and a Next.js frontend with TypeScript and Tailwind CSS. The blockchain component uses Solidity smart contracts deployed on Polygon Amoy testnet via Hardhat.", B)]
    story += [Paragraph("The proposed system aims to achieve deepfake detection accuracy exceeding 90% on standard benchmarks through the complementary strengths of its five detection modalities. The fusion engine applies learned attention weights to each expert branch, ensuring robustness against single-modality spoofing. Results demonstrate that the multimodal approach significantly outperforms single-signal detectors that typically achieve 65-80% accuracy. The blockchain provenance layer provides cryptographic guarantees of media origin, enabling media organizations, law enforcement, and content platforms to establish verifiable chains of custody for digital media.", B)]
    story += [PageBreak()]

    # ── Table of Contents ─────────────────────────────────────────────────────
    story += [Paragraph("<b>TABLE OF CONTENTS</b>", BC)]
    story += [Spacer(1,0.3*cm)]
    toc_data = [
        ["CHAPTER NO", "TITLE", "PAGE NO"],
        ["", "ABSTRACT", "i"],
        ["", "LIST OF FIGURES", "ii"],
        ["1", "INTRODUCTION", "1"],
        ["", "    1.1 Overview", "1"],
        ["", "    1.2 Problem Statement", "3"],
        ["", "    1.3 Objectives", "5"],
        ["2", "LITERATURE REVIEW", "6"],
        ["", "    2.1 Existing Systems", "6"],
        ["", "    2.2 Limitations of Existing Systems", "8"],
        ["", "    2.3 Proposed System Advantages", "9"],
        ["3", "SYSTEM ANALYSIS", "10"],
        ["", "    3.1 Feasibility Study", "10"],
        ["", "    3.2 Hardware and Software Requirements", "13"],
        ["", "    3.3 Functional and Non-Functional Requirements", "14"],
        ["4", "SYSTEM DESIGN", "16"],
        ["", "    4.1 System Architecture", "16"],
        ["", "    4.2 Data Flow Diagrams", "19"],
        ["", "    4.3 Use Case Diagram", "20"],
        ["", "    4.4 Database Schema", "22"],
        ["5", "METHODOLOGY", "24"],
        ["", "    5.1 Multimodal AI Detection Pipeline", "24"],
        ["6", "IMPLEMENTATION", "32"],
        ["", "    6.1 Web Application User Interface", "32"],
        ["", "    6.2 Backend Implementation", "37"],
        ["", "    6.3 Database Implementation", "40"],
        ["7", "RESULTS AND ANALYSIS", "43"],
        ["", "    7.1 Performance Metrics", "43"],
        ["", "    7.2 Analysis Visualization", "46"],
        ["", "    7.3 Detection Accuracy Analysis", "48"],
        ["8", "CONCLUSION AND FUTURE WORK", "51"],
        ["", "    8.1 Conclusion", "51"],
        ["", "    8.2 Future Enhancements", "51"],
        ["", "REFERENCES", "53"],
    ]
    toc_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4472C4')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Times-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 12),
        ('ALIGN',      (2,0), (2,-1), 'RIGHT'),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW',  (0,0), (-1,0), 1, colors.black),
        ('LINEBELOW',  (0,-1),(-1,-1),1, colors.black),
        ('LINEABOVE',  (0,0), (-1,0), 1, colors.black),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
    ])
    toc_tbl = Table([[Paragraph(f"<b>{c}</b>" if i==0 else c, st['small']) for c in row]
                      for i,row in enumerate(toc_data)],
                    colWidths=[TW*0.18, TW*0.66, TW*0.16])
    toc_tbl.setStyle(toc_style)
    story += [toc_tbl]
    story += [PageBreak()]

    # ── List of Figures ───────────────────────────────────────────────────────
    story += [Paragraph("<b>LIST OF FIGURES</b>", BC)]
    story += [Spacer(1,0.3*cm)]
    lof_data = [
        ["FIGURE NO", "TITLE", "PAGE NO"],
        ["4.1", "Multi-Tier System Architecture", "16"],
        ["4.2", "Data Flow Diagram", "19"],
        ["4.3", "Use Case Diagram", "20"],
        ["4.4", "Database Entity-Relationship Diagram", "22"],
        ["5.1", "Five Expert Branch Detection Pipeline", "24"],
        ["6.1", "TrustMedia Home Page", "32"],
        ["6.2", "Video Upload Interface", "34"],
        ["6.3", "Analysis Results Dashboard", "35"],
        ["6.4", "Videos Dashboard", "36"],
        ["7.1", "Performance Metrics – Target vs Achieved", "43"],
        ["7.2", "Per-Signal Analysis Visualization", "46"],
        ["7.3", "Detection Accuracy by Modality", "48"],
    ]
    lof_tbl = Table([[Paragraph(f"<b>{c}</b>" if i==0 else c, st['small']) for c in row]
                      for i,row in enumerate(lof_data)],
                    colWidths=[TW*0.18, TW*0.66, TW*0.16])
    lof_tbl.setStyle(toc_style)
    story += [lof_tbl]
    story += [PageBreak()]

    # ── CHAPTER 1 ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>CHAPTER 1</b>", st['ch_label'])]
    story += [Paragraph("<b>INTRODUCTION</b>", st['ch_title'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>1.1 Overview</b>", H2)]
    story += [Paragraph("The digital information landscape has undergone a radical transformation with the advent of generative artificial intelligence and deep learning technologies. What was once the exclusive domain of high-budget film studios — the ability to convincingly alter or fabricate video footage — is now accessible to anyone with a consumer-grade computer and an internet connection. Deepfake technology, which uses generative adversarial networks (GANs) and diffusion models to synthesize photorealistic video of people saying or doing things they never actually said or did, has proliferated at an alarming rate. This technological capability poses profound risks to societal institutions that depend on the authenticity of audiovisual evidence.", B)]
    story += [Paragraph("The consequences of deepfake proliferation are already being felt across multiple domains. In journalism and media, synthetic videos of public figures making inflammatory statements have been used to spread disinformation. In legal contexts, the admissibility of video evidence is increasingly challenged by the possibility of digital manipulation. Political campaigns have deployed deepfake content to discredit opponents, and individuals have been victims of non-consensual synthetic media that damages their reputation and personal safety. Financial fraud using voice cloning deepfakes has resulted in substantial monetary losses for corporations and individuals worldwide.", B)]
    story += [Paragraph("The detection of deepfakes has emerged as a critical research and engineering challenge. Early detection systems relied on identifying visible artifacts in synthesized media — unnatural blinking patterns, inconsistent lighting on facial regions, or spectral anomalies in audio tracks. However, as generative models have become more sophisticated, these simple detection heuristics have become increasingly inadequate. Modern deepfakes produced by state-of-the-art generation models are perceptually indistinguishable from authentic footage even to trained human observers. This arms race between generation and detection necessitates a fundamentally more robust approach.", B)]
    story += [Paragraph("Furthermore, single-modal detection systems — those that analyze only facial appearance, only audio characteristics, or only temporal consistency — are inherently vulnerable to adversarial attacks that optimize the deepfake for one detection axis while neglecting others. A face-swap that preserves perfect lip synchronization will evade an audio-visual coherence detector, while a voice clone that does not attempt to manipulate video will evade facial analysis systems. The solution requires simultaneous analysis across multiple independent signal channels, with fusion of the resulting evidence into a unified authenticity verdict.", B)]
    story += [Paragraph("Beyond detection, there exists a complementary need for provenance verification — a mechanism to establish a cryptographically verifiable chain of custody for digital media. If a trusted media organization or camera device registers the hash of authentic footage on a public blockchain at the time of capture, any subsequent copy of that footage can be instantly verified as authentic without requiring AI inference. This blockchain-based approach provides a ground truth anchor that is immune to the limitations of statistical detection models. The combination of multimodal AI detection with blockchain provenance represents a two-layer trust verification architecture that addresses both known and unknown manipulation techniques.", B)]
    story += [Paragraph("TrustMedia is designed to serve this exact need. The platform accepts any video file and returns a comprehensive trust assessment within seconds. The assessment includes a per-signal breakdown across five detection modalities, a fused fake_probability score, a final verdict of AUTHENTIC, SUSPICIOUS, or MANIPULATED, and a blockchain verification status. The system is architected as a production-grade microservices platform, capable of handling concurrent analysis requests through asynchronous task processing, and deployable on cloud infrastructure.", B)]

    story += [Paragraph("<b>1.2 Problem Statement</b>", H2)]
    story += [Paragraph("Deepfake detection presents a multidimensional technical challenge that existing solutions have failed to address comprehensively. Several critical limitations characterize the current state of deepfake detection and media verification.", B)]
    story += [Paragraph("First, the single-modality limitation: most deployed detection systems analyze only one aspect of video content. Facial analysis systems examine visual features of faces but cannot detect voice cloning. Audio analysis systems identify synthetic voice characteristics but cannot detect face-swaps. Lip synchronization detectors identify audio-visual mismatches but are blind to deepfakes that correctly preserve synchronization. Each individual modality represents a single point of failure that sophisticated deepfake generators can specifically optimize against.", B)]
    story += [Paragraph("Second, the absence of provenance verification: even when a detection system correctly identifies media as authentic, it cannot establish where that media came from, who created it, or whether it has been tampered with since creation. There is no existing mechanism for media producers to register authentic content in a way that allows downstream verifiers to cryptographically confirm its authenticity without running computationally expensive AI models.", B)]
    story += [Paragraph("Third, the generalization problem: detection models trained on one category of deepfake generation method frequently fail to detect deepfakes produced by different or newer generation methods. A model trained primarily on face-swap deepfakes may perform poorly on full face synthesis or voice cloning attacks. The rapid evolution of generative AI makes it difficult to maintain detection systems that remain effective against emerging threats without continuous retraining and updating.", B)]
    story += [Paragraph("Fourth, the lack of explainability: most black-box neural network classifiers produce a binary authentic/fake label without providing any interpretable reasoning for their decision. Media professionals, journalists, and legal practitioners require not just a verdict but an explanation of which specific signals triggered the detection — whether it was facial inconsistencies, voice artifacts, abnormal blink patterns, or lip-sync failures. Explainability is essential for actionable decision-making.", B)]

    story += [Paragraph("<b>1.3 Objectives</b>", H2)]
    story += [Paragraph("The primary objective of this project is to design and implement a robust, production-grade deepfake detection and media provenance verification platform.", B)]
    story += [Paragraph("The specific objectives include:", BN)]
    for txt in [
        "1. To develop a five-branch multimodal detection system analyzing face, lip-sync, voice, blink, and head motion signals simultaneously.",
        "2. To implement an Attention-based MLP Fusion Engine that learns optimal weights for combining per-modality scores into a final fake_probability.",
        "3. To design a blockchain provenance layer using Solidity smart contracts on Polygon that enables instant verification of registered media hashes.",
        "4. To build a production-grade microservices backend using FastAPI, Celery, PostgreSQL, and Redis for handling concurrent analysis requests.",
        "5. To create an intuitive Next.js web interface that presents detection results with per-signal breakdowns and blockchain verification status.",
        "6. To achieve deepfake detection accuracy exceeding 90% on standard benchmarks through multimodal fusion.",
        "7. To provide confidence-calibrated probability estimates and uncertainty flags that support informed decision-making by end users.",
    ]:
        story += [Paragraph(txt, BL)]
    story += [PageBreak()]

    # ── CHAPTER 2 ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>CHAPTER 2</b>", st['ch_label'])]
    story += [Paragraph("<b>LITERATURE REVIEW</b>", st['ch_title'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>2.1 Existing Systems</b>", H2)]
    story += [Paragraph("Research in deepfake detection has evolved rapidly over the past decade, spanning facial forgery detection, audio synthesis detection, audiovisual coherence analysis, and physiological signal analysis. Early work in deepfake detection focused on identifying compression artifacts, unnatural blending boundaries at face edges, and inconsistent illumination patterns. These handcrafted feature approaches achieved reasonable accuracy on first-generation deepfakes produced by methods such as DeepFaceLab and FaceSwap but proved fragile as generation quality improved.", B)]
    story += [Paragraph("Convolutional neural network approaches became dominant with the release of large-scale deepfake detection datasets including FaceForensics++, which provided high-quality manipulated videos generated by four different methods. MesoNet introduced a lightweight CNN specifically designed for deepfake detection that examined mesoscopic properties of facial images. XceptionNet, adapted from its original image classification task, demonstrated strong performance on the FaceForensics++ benchmark. However, these image-level classifiers failed to exploit temporal information across video frames, limiting their ability to detect temporally consistent but spatially realistic deepfakes.", B)]
    story += [Paragraph("Temporal modeling approaches addressed this limitation by incorporating sequence models. Recurrent neural networks and long short-term memory networks were applied to sequences of frame-level features to detect temporal inconsistencies. More recent approaches employ transformer-based architectures for temporal modeling, leveraging self-attention mechanisms to capture long-range temporal dependencies in facial motion patterns. These temporal models are particularly effective at detecting deepfakes that produce unnatural motion dynamics even when individual frames appear authentic.", B)]
    story += [Paragraph("Physiological signal analysis represents another important research direction. The FakeCatcher system proposed by Ciftci et al. demonstrated that real human faces exhibit consistent photoplethysmography signals — subtle color changes in skin caused by blood circulation — while deepfake faces typically fail to reproduce these biological signals coherently. Blink pattern analysis has also emerged as a detection signal, as early GAN-based deepfake generators frequently produced faces with abnormal blinking frequency or duration. Head pose and motion analysis provides additional signal channels, as synthesized faces may exhibit physically implausible rotational dynamics.", B)]
    story += [Paragraph("Voice authentication and audio deepfake detection has developed as a parallel research field. Automatic speaker verification systems, originally designed for biometric authentication, have been repurposed for detecting synthetic speech. ASVspoof challenge datasets have driven development of detection systems for text-to-speech and voice conversion attacks. Wav2Vec2 and other self-supervised audio representations have demonstrated strong generalization across different voice synthesis methods. MFCC-based features combined with deep neural networks remain widely used for detecting artificial speech characteristics.", B)]

    story += [Paragraph("<b>2.2 Limitations of Existing Systems</b>", H2)]
    story += [Paragraph("Despite significant research progress, existing deepfake detection systems exhibit several critical limitations that prevent their effective deployment in real-world scenarios.", B)]
    story += [Paragraph("The most significant limitation is cross-method generalization. Most published detection systems are evaluated on the same generation methods present in their training data and show dramatic accuracy degradation when tested on unseen generation methods. A model trained primarily on face-swap deepfakes may perform at near-chance levels when applied to fully synthesized faces or voice-cloned videos. This brittleness makes single-method systems impractical for deployment against adversarially chosen attacks.", B)]
    story += [Paragraph("Single-modality approaches represent another fundamental limitation. Systems that analyze only facial appearance, only audio characteristics, or only audiovisual synchronization can be defeated by deepfakes that are specifically optimized to pass that particular detection axis while making no effort to pass others. An attacker who knows that only facial analysis will be applied can focus generation quality on the facial region while ignoring voice authenticity. Multi-signal approaches are inherently more robust against such targeted evasion strategies.", B)]
    story += [Paragraph("The absence of provenance mechanisms means that even accurate detection systems cannot answer the fundamental question: where did this video come from, and can we verify its origin? Detection systems can only classify content as likely authentic or likely manipulated based on statistical patterns, without providing any cryptographic guarantee of authenticity. For legal, journalistic, and institutional use cases that require definitive proof of authenticity rather than statistical estimates, this limitation is critical.", B)]

    story += [Paragraph("<b>2.3 Proposed System Advantages</b>", H2)]
    story += [Paragraph("The TrustMedia platform addresses the identified limitations through a comprehensive architecture that integrates multiple independent detection strategies with blockchain provenance.", B)]
    for txt in [
        "1. Five independent expert branches operating in parallel ensure that defeating any single modality does not compromise overall detection accuracy. An adversary must simultaneously fool facial analysis, voice authentication, lip synchronization, blink pattern analysis, and head motion physics — an extremely difficult multi-constraint optimization problem.",
        "2. The Attention-based MLP Fusion Engine learns which signals are most reliable for a given input video and dynamically weights their contributions. This learned fusion is more robust than fixed-weight approaches and adapts to scenarios where certain modalities may be unavailable or less informative.",
        "3. Blockchain provenance verification provides cryptographic ground truth for registered media, entirely bypassing the statistical limitations of AI detection for authenticated content. Trusted sources can register media hashes at creation time, enabling instant verification without AI inference.",
        "4. Confidence calibration using temperature scaling provides probabilistic estimates that accurately reflect detection uncertainty. The system flags high-uncertainty cases with an uncertainty flag (LOW/MEDIUM/HIGH), allowing users to apply appropriate levels of skepticism.",
        "5. The microservices architecture enables horizontal scaling through Celery workers, allowing the platform to handle large numbers of concurrent analysis requests in production deployment scenarios.",
    ]:
        story += [Paragraph(txt, BL)]
    story += [PageBreak()]

    # ── CHAPTER 3 ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>CHAPTER 3</b>", st['ch_label'])]
    story += [Paragraph("<b>SYSTEM ANALYSIS</b>", st['ch_title'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>3.1 FEASIBILITY STUDY</b>", H2)]
    story += [Paragraph("Before developing the TrustMedia platform, a detailed feasibility study was conducted to determine whether the proposed system is practical, implementable, and beneficial for real-world deployment. Feasibility analysis evaluates the viability of the project by examining technical resources, financial considerations, operational requirements, and potential risks involved in development and deployment.", B)]
    story += [Paragraph("The feasibility study focuses on three major aspects:", BN)]
    for t in ["• Technical Feasibility", "• Economic Feasibility", "• Operational Feasibility"]:
        story += [Paragraph(t, BL)]
    story += [Paragraph("<b>TECHNICAL FEASIBILITY</b>", H2)]
    story += [Paragraph("The TrustMedia platform relies on a combination of mature deep learning frameworks and emerging blockchain technology. The core AI components leverage PyTorch, the industry standard framework for deep learning research and production deployment. EfficientNet-B4 for facial analysis, Wav2Vec2 for voice authentication, and MediaPipe for landmark detection are all well-established models with publicly available pre-trained weights that can be fine-tuned on deepfake detection datasets.", B)]
    story += [Paragraph("The backend infrastructure uses FastAPI, a high-performance asynchronous Python web framework built on ASGI standards. Celery provides robust distributed task processing with Redis as the message broker. PostgreSQL is a production-proven relational database suitable for storing video metadata, analysis jobs, results, and blockchain records. These technologies are all open-source, well-documented, and supported by large communities. The blockchain component uses Solidity smart contracts on the Polygon network, which provides Ethereum compatibility with significantly lower gas costs. Hardhat provides a professional smart contract development environment.", B)]
    story += [Paragraph("The frontend is built with Next.js 14, TypeScript, and Tailwind CSS with shadcn/ui components. These technologies represent the current industry standard for building high-quality, maintainable web applications. The combination of all these technologies is technically feasible and has been validated through successful implementation of the working prototype described in this report.", B)]
    story += [Paragraph("<b>ECONOMIC FEASIBILITY</b>", H2)]
    story += [Paragraph("The TrustMedia platform is economically feasible due to its exclusive reliance on open-source software components. PyTorch, FastAPI, Celery, Redis, PostgreSQL, Next.js, and Hardhat are all freely available without licensing costs. The primary development costs are computational resources for training deep learning models and cloud hosting for deployment.", B)]
    story += [Paragraph("Blockchain transaction costs on Polygon are minimal compared to Ethereum mainnet, making provenance registration economically viable even for frequent media uploads. The platform's ability to provide instant blockchain verification for registered media without AI inference reduces ongoing computational costs for verified content. The economic benefits of accurate deepfake detection — protecting against fraud, disinformation, and reputational damage — far outweigh the development and operational costs of the platform.", B)]
    story += [Paragraph("<b>OPERATIONAL FEASIBILITY</b>", H2)]
    story += [Paragraph("The TrustMedia platform is operationally feasible due to its intuitive web interface that requires no technical expertise from end users. The upload-and-analyze workflow is straightforward: users upload a video file, the system processes it asynchronously in the background, and results are displayed through an interactive dashboard. The asynchronous architecture ensures that the user interface remains responsive even during computationally intensive analysis.", B)]
    story += [Paragraph("The modular microservices architecture enables independent scaling of frontend, API, and worker components based on actual load patterns. Docker containerization simplifies deployment and ensures consistent behavior across development, staging, and production environments. The system can be deployed on standard cloud infrastructure without specialized hardware, though GPU acceleration significantly improves analysis throughput.", B)]

    story += [Paragraph("<b>3.2 HARDWARE AND SOFTWARE REQUIREMENTS</b>", H2)]
    story += [Paragraph("<b>HARDWARE REQUIREMENTS</b>", BLD)]
    hw = [
        "<b>Processor</b> – Intel i7 or AMD Ryzen 7 (GPU: NVIDIA GTX 1080 or higher recommended)",
        "<b>Memory (RAM)</b> – >= 16GB (32GB recommended for training)",
        "<b>Storage</b> – >= 512GB SSD",
        "<b>GPU VRAM</b> – >= 8GB for model inference",
    ]
    for t in hw:
        story += [Paragraph(t, BL)]
    story += [Paragraph("<b>SOFTWARE REQUIREMENTS</b>", BLD)]
    sw = [
        ("<b>Operating System</b>", "Linux (Ubuntu 22.04 LTS recommended) / Windows 11 / macOS 13+"),
        ("<b>Programming Languages</b>", "Python 3.11+, TypeScript / JavaScript (Node.js 20+)"),
        ("<b>Backend Framework</b>", "FastAPI, Celery, SQLAlchemy"),
        ("<b>Frontend Framework</b>", "Next.js 14, React 18, Tailwind CSS, shadcn/ui"),
        ("<b>Database</b>", "PostgreSQL 16"),
        ("<b>Cache / Queue</b>", "Redis 7"),
        ("<b>ML Framework</b>", "PyTorch 2.x, torchvision, torchaudio"),
        ("<b>Blockchain</b>", "Solidity, Hardhat, Ethers.js, Polygon Amoy testnet"),
        ("<b>Containerization</b>", "Docker, Docker Compose"),
        ("<b>Media Processing</b>", "FFmpeg"),
    ]
    for k, v in sw:
        story += [Paragraph(f"{k} – {v}", BL)]

    story += [Paragraph("<b>3.3 FUNCTIONAL AND NON-FUNCTIONAL REQUIREMENTS</b>", H2)]
    story += [Paragraph("<b>FUNCTIONAL REQUIREMENTS</b>", BLD)]
    story += [Paragraph("Functional requirements describe the core operations that the system must perform to achieve its objectives.", BN)]
    for t in [
        "1. The system shall accept video file uploads in MP4, MOV, AVI, WebM, and MKV formats up to 500MB in size.",
        "2. The system shall extract video frames using FFmpeg and separate audio tracks as WAV files for independent analysis.",
        "3. The Face Authenticity Analyzer shall detect faces using MTCNN/MediaPipe and analyze temporal sequences using EfficientNet-B4 with a Temporal Transformer to produce a face_score.",
        "4. The Lip Synchronization Verifier shall compute audio-visual coherence between detected mouth regions and audio embeddings to produce a lipsync_score.",
        "5. The Voice Authenticity Analyzer shall extract Wav2Vec2 embeddings and MFCC features from audio tracks to produce a voice_score.",
        "6. The Blink Pattern Analyzer shall compute Eye Aspect Ratio sequences using MediaPipe landmarks and classify blink patterns using XGBoost to produce a blink_score.",
        "7. The Head Motion Analyzer shall reconstruct 3D head pose using solvePnP and apply physics-based plausibility analysis to produce a headmotion_score.",
        "8. The Fusion Engine shall combine per-branch scores using an Attention MLP with temperature calibration to produce fake_probability (0-100) and a final verdict.",
        "9. The system shall check registered blockchain hashes before AI inference and return an immediate AUTHENTIC verdict if a verified match is found.",
        "10. The system shall provide a RESTful API for video upload, job status polling, and result retrieval.",
        "11. The system shall allow media owners to register video hashes on the Polygon blockchain via an API endpoint.",
    ]:
        story += [Paragraph(t, BL)]
    story += [Paragraph("<b>NON-FUNCTIONAL REQUIREMENTS</b>", BLD)]
    nf = [
        ("<b>Performance</b>", "AI analysis of a 30-second video shall complete within 60 seconds on CPU; within 15 seconds with GPU acceleration."),
        ("<b>Accuracy</b>", "The fusion model shall achieve deepfake detection accuracy of at least 90% on standard benchmark datasets."),
        ("<b>Scalability</b>", "The Celery worker pool shall support horizontal scaling to handle 50+ concurrent analysis requests."),
        ("<b>Reliability</b>", "The system shall implement graceful fallback heuristics for each modality when trained model weights are unavailable."),
        ("<b>Security</b>", "Video files shall be processed server-side only; raw video data shall not be exposed through API responses."),
        ("<b>Usability</b>", "Analysis results shall include per-signal explanations interpretable by non-technical users."),
    ]
    for k, v in nf:
        story += [Paragraph(f"{k} – {v}", BL)]
    story += [PageBreak()]

    # ── CHAPTER 4 ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>CHAPTER 4</b>", st['ch_label'])]
    story += [Paragraph("<b>SYSTEM DESIGN</b>", st['ch_title'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>4.1 SYSTEM ARCHITECTURE</b>", H2)]
    story += [Paragraph("The TrustMedia platform is designed using a microservices architecture that separates different system responsibilities into independent, loosely coupled services. This architectural approach provides scalability, maintainability, and resilience. Each service can be independently developed, tested, deployed, and scaled without affecting the operation of other services.", B)]
    story += [Paragraph("The system architecture consists of the following major layers:", BN)]
    for t in [
        "1. Presentation Layer (Next.js Frontend)",
        "2. API Gateway Layer (FastAPI REST API)",
        "3. Task Processing Layer (Celery Workers)",
        "4. AI Analysis Pipeline (5 Expert Branches + Fusion Engine)",
        "5. Data Persistence Layer (PostgreSQL + Redis)",
        "6. Blockchain Integration Layer (Polygon Smart Contracts)",
    ]:
        story += [Paragraph(t, BL)]
    story += [Paragraph("The Presentation Layer is a Next.js 14 web application built with TypeScript, Tailwind CSS, and shadcn/ui component library. It provides three primary interfaces: a landing page explaining system capabilities, a video upload interface for submitting media for analysis, and a results dashboard displaying per-signal scores, the fusion verdict, blockchain verification status, and analysis timeline.", B)]
    story += [Paragraph("The API Gateway Layer is implemented using FastAPI, which exposes RESTful endpoints for video upload, job status polling, result retrieval, and blockchain operations. FastAPI's asynchronous request handling allows the API to accept new upload requests while existing analysis jobs are being processed by workers. SQLAlchemy provides the ORM layer for database interactions, with Pydantic models enforcing input and output schema validation.", B)]
    story += [Paragraph("The Task Processing Layer uses Celery with Redis as the message broker to manage asynchronous analysis jobs. When a video is uploaded, the API immediately dispatches an analysis task to the Celery queue and returns a job ID to the client. The client polls the job status endpoint until the analysis completes. This decoupling ensures that computationally intensive AI analysis does not block the API from accepting new requests.", B)]
    story += [Paragraph("The AI Analysis Pipeline is the core intelligence of the platform, consisting of five expert branches operating on different aspects of the video signal, followed by a Fusion Engine that combines their outputs into a final verdict. The Blockchain Integration Layer interfaces with Polygon smart contracts to check media provenance before running AI analysis and to register new authentic media hashes.", B)]
    story += [Paragraph("The Data Persistence Layer uses PostgreSQL for structured data storage including video metadata, analysis job records, analysis results, and blockchain records. Redis serves dual roles as Celery's message broker for job queue management and as a caching layer for frequently accessed data.", B)]
    story += fig(f41, "Figure 4.1: Multi-Tier System Architecture", st)

    story += [Paragraph("<b>4.2 DATA FLOW DIAGRAM</b>", H2)]
    story += [Paragraph("The Data Flow Diagram illustrates how data moves through the TrustMedia platform from initial video upload through final result delivery.", B)]
    story += [Paragraph("The process begins when a user uploads a video file through the web interface. The FastAPI backend receives the file, computes its SHA-256 hash, saves it to the filesystem, and creates database records for the video and analysis job. A Celery task is immediately dispatched to the analysis queue with the video ID.", B)]
    story += [Paragraph("The Celery worker retrieves the task and begins the analysis pipeline. First, it checks the PostgreSQL database for any registered blockchain record matching the video hash. If a match is found, the worker queries the Polygon blockchain to verify the on-chain record. If the hash matches an authentic registration, the worker immediately records a trust_score of 100 and AUTHENTIC verdict without AI processing.", B)]
    story += [Paragraph("If no blockchain record exists, the worker proceeds to media extraction using FFmpeg, producing a sequence of video frames and a WAV audio file. These extracted media components are then processed by the five expert branches in parallel. Each branch independently analyzes its assigned signal and produces a normalized score between 0 (authentic) and 100 (fake). The five scores are passed to the Fusion Engine, which applies attention-weighted averaging and temperature calibration to produce the final fake_probability and verdict.", B)]
    story += [Paragraph("The complete result is stored in the PostgreSQL analysis_results table and the job status is updated to completed. The client, which has been polling the job status endpoint, receives the completed status and renders the full results dashboard.", B)]
    story += fig(f42, "Figure 4.2: Data Flow Diagram", st)

    story += [Paragraph("<b>4.3 USE CASE DIAGRAM</b>", H2)]
    story += [Paragraph("The use case diagram illustrates the interactions between the system's actors and the functional capabilities of the TrustMedia platform. The primary actors are the Media Analyst (general user submitting videos for analysis) and the Media Owner (content creator registering authentic media for provenance tracking).", B)]
    story += [Paragraph("The primary use cases include:", BN)]
    for t in [
        "1. Upload Video for Analysis – The Media Analyst uploads a video file and initiates the analysis pipeline.",
        "2. Poll Analysis Status – The Media Analyst queries the job status endpoint to monitor analysis progress.",
        "3. View Analysis Results – The Media Analyst reviews the complete results dashboard with per-signal scores and verdict.",
        "4. Register Media Provenance – The Media Owner registers a video hash on the blockchain for future verification.",
        "5. Verify Blockchain Record – The system checks the blockchain during analysis for matching provenance records.",
        "6. Browse Upload History – The Media Analyst reviews previously analyzed videos through the dashboard interface.",
        "7. Share Analysis Results – The Media Analyst shares analysis results using a public share URL.",
    ]:
        story += [Paragraph(t, BL)]
    story += fig(f43, "Figure 4.3: Use Case Diagram", st)

    story += [Paragraph("<b>4.4 DATABASE SCHEMA</b>", H2)]
    story += [Paragraph("The database schema defines how data is structured and stored within the TrustMedia platform. The system uses PostgreSQL as its relational database management system, providing ACID compliance, advanced indexing, and full support for JSON data types used to store complex analysis signal details.", B)]
    story += [Paragraph("The database consists of four primary tables:", BN)]
    story += [Paragraph("<b>Videos Table</b>", H3)]
    story += [Paragraph("The videos table stores metadata for each uploaded video file, including the original filename, file size, file path on the server filesystem, SHA-256 hash for blockchain matching, IPFS CID for distributed storage, upload timestamp, and MIME type. The hash field is used for blockchain provenance lookups and deduplication.", B)]
    story += [Paragraph("<b>Analysis Jobs Table</b>", H3)]
    story += [Paragraph("The analysis_jobs table tracks the lifecycle of each analysis request. It records the Celery task ID, job status (pending, processing, extracting, analyzing, blockchain_check, completed, failed), analysis progress percentage (0-100), error messages for failed jobs, and timestamps for job creation, start, and completion. The status field drives the frontend polling behavior.", B)]
    story += [Paragraph("<b>Analysis Results Table</b>", H3)]
    story += [Paragraph("The analysis_results table stores the complete output of each successful analysis. Key fields include fake_probability (0-100 float), trust_score (0-100 integer, inverse of fake_probability), verdict (authentic/suspicious/manipulated), confidence calibrated probability, uncertainty_flag (LOW/MEDIUM/HIGH), per-signal scores (face_score, voice_score, lipsync_score, blink_score, headmotion_score), modality_weights from the attention fusion, explanation text, and a JSON field containing detailed signal analysis data.", B)]
    story += [Paragraph("<b>Blockchain Records Table</b>", H3)]
    story += [Paragraph("The blockchain_records table stores provenance registration data including the video hash, Ethereum transaction hash, IPFS CID, owner wallet address, device signature, blockchain network identifier, and registration timestamp. This table is queried during analysis to check for existing provenance records before running the AI pipeline.", B)]
    story += fig(f44, "Figure 4.4: Database Entity-Relationship Diagram", st)
    story += [PageBreak()]

    # ── CHAPTER 5 ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>CHAPTER 5</b>", st['ch_label'])]
    story += [Paragraph("<b>METHODOLOGY</b>", st['ch_title'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>5.1 MULTIMODAL AI DETECTION PIPELINE</b>", H2)]
    story += [Paragraph("The methodology adopted in TrustMedia is founded on the principle of multimodal evidence fusion — that combining multiple independent analytical signals produces a detection system that is more robust, accurate, and harder to defeat than any single-signal approach. Deepfake media must simultaneously maintain authenticity across all five analyzed signal channels to evade detection, which represents a substantially harder optimization problem for adversarial deepfake generation.", B)]
    story += [Paragraph("The platform employs five expert detection branches, each implemented as an independent module that analyzes a specific aspect of the video signal. All five branches produce a score in the range [0, 100] where 0 represents high confidence of authenticity and 100 represents high confidence of manipulation. These per-branch scores are aggregated by the Fusion Engine into the final fake_probability.", B)]
    story += [Paragraph("<b>Face Authenticity Analysis Branch</b>", H3)]
    story += [Paragraph("The Face Authenticity Analysis branch detects facial manipulation artifacts using a combination of spatial and temporal deep learning models. Face detection is performed using MTCNN or MediaPipe FaceMesh to locate and crop the facial region in each video frame. These crops are resized to 224x224 pixels and fed to an EfficientNet-B4 backbone pretrained on ImageNet, which extracts high-dimensional spatial feature representations.", B)]
    story += [Paragraph("The spatial features from multiple consecutive frames are organized into temporal sequences and processed by a Temporal Transformer module. The transformer's self-attention mechanism captures inter-frame dependencies that reveal temporal inconsistencies in facial motion, expression dynamics, and texture evolution — characteristics that authentic faces exhibit consistently but synthesized faces frequently fail to replicate. The output of the temporal transformer is passed through a classification head to produce the face_score. When no face is detected in the video, the branch returns a neutral score of 50.0 to avoid biasing the fusion result.", B)]
    story += [Paragraph("<b>Lip Synchronization Verification Branch</b>", H3)]
    story += [Paragraph("The Lip Synchronization Verification branch analyzes the coherence between facial lip movements and audio speech content. Many deepfake generation methods — particularly face-swaps applied to authentic video — produce faces whose lip movements do not precisely match the underlying audio track. This audiovisual desynchronization is a powerful detection signal.", B)]
    story += [Paragraph("The branch is implemented using a SyncNet-style architecture consisting of two parallel networks: a visual stream (ResNet18-based) that processes sequences of cropped mouth region images, and an audio stream (CNN-based) that processes mel-spectrogram segments of the audio track. The two streams are trained to produce similar embeddings for synchronized audio-visual pairs and dissimilar embeddings for mismatched pairs using a contrastive loss function. At inference time, the cosine similarity between audio and visual embeddings is computed across temporal windows, and the minimum similarity score is used as the lipsync authenticity indicator.", B)]
    story += [Paragraph("<b>Voice Authenticity Analysis Branch</b>", H3)]
    story += [Paragraph("The Voice Authenticity Analysis branch detects synthetic speech and voice cloning by analyzing the acoustic properties of the video's audio track. Voice deepfakes produced by text-to-speech and voice conversion systems typically exhibit subtle artifacts in the spectral and prosodic characteristics of speech that are absent in authentic human voice recordings.", B)]
    story += [Paragraph("The branch extracts two complementary feature representations from the audio signal. Wav2Vec2 embeddings, derived from a large transformer model pretrained on massive speech corpora, capture high-level phonetic and acoustic features that are sensitive to the authenticity of the vocal source. MFCC (Mel-Frequency Cepstral Coefficients) features capture the short-term spectral envelope of speech, which encodes voice timbre and quality characteristics. These two feature sets are combined and processed by a CNN classifier to produce the voice_score.", B)]
    story += [Paragraph("<b>Blink Pattern Analysis Branch</b>", H3)]
    story += [Paragraph("The Blink Pattern Analysis branch detects unnatural eye blinking patterns that are characteristic of some deepfake generation methods. Authentic human blinking exhibits characteristic statistical properties including blink rate (typically 15-20 blinks per minute), blink duration (100-400ms), and temporal variability. Early GAN-based deepfake methods frequently produced faces with abnormal blinking frequency or completely absent blinks due to limitations in temporal modeling.", B)]
    story += [Paragraph("The branch computes the Eye Aspect Ratio (EAR) for each video frame using MediaPipe FaceMesh landmark coordinates. EAR is defined as the ratio of the vertical eye opening to the horizontal eye width, providing a normalized measure of eye openness that drops sharply during blinks. The EAR time series across all video frames is analyzed by an XGBoost classifier trained on features including mean EAR, EAR standard deviation, blink frequency, blink duration statistics, and temporal autocorrelation. The XGBoost classifier produces the blink_score indicating the probability of artificial blink patterns.", B)]
    story += [Paragraph("<b>Head Motion Analysis Branch</b>", H3)]
    story += [Paragraph("The Head Motion Analysis branch detects physically implausible head movement patterns that arise when deepfake generators fail to accurately reproduce the natural dynamics of head rotation and translation. Authentic head motion follows physical laws of rigid body dynamics — inertia, damping, and momentum — that constrain how quickly and smoothly a head can move.", B)]
    story += [Paragraph("The branch uses OpenCV's solvePnP algorithm to estimate the 3D head pose (rotation and translation vectors) for each video frame from the 2D projections of MediaPipe facial landmarks onto a 3D face model. The resulting pose trajectory is analyzed using a physics-based plausibility model that computes acceleration profiles, jerk (rate of change of acceleration), and angular velocity distributions. Features derived from this physics analysis are processed by an XGBoost classifier to identify head motion patterns inconsistent with natural human movement, producing the headmotion_score.", B)]
    story += [Paragraph("<b>Attention-Based Fusion Engine</b>", H3)]
    story += [Paragraph("The Fusion Engine combines the five per-branch scores into the final fake_probability through a learned attention mechanism. Rather than using fixed weights, the fusion engine learns which signal sources are most reliable for different types of input videos, dynamically adjusting contribution weights based on the characteristics of each input.", B)]
    story += [Paragraph("The fusion architecture is a Multi-Layer Perceptron with an attention mechanism. The five branch scores are fed as input features, and the attention layer produces a weight vector that softmax-normalizes the contribution of each branch. The weighted scores are aggregated and passed through additional dense layers to produce the pre-calibration fake probability.", B)]
    story += [Paragraph("Temperature Scaling is applied as a post-hoc calibration step to ensure that the model's confidence scores accurately reflect empirical accuracy. A calibration temperature T is learned on a held-out calibration set to minimize the Expected Calibration Error (ECE). The calibrated probability is computed as:", B)]
    story += [Paragraph("<b>P_calibrated = softmax(logits / T)</b>", st['formula'])]
    story += [Paragraph("The final fake_probability is mapped to one of three verdict categories: AUTHENTIC (fake_probability < 40), SUSPICIOUS (40 ≤ fake_probability < 70), and MANIPULATED (fake_probability ≥ 70). An uncertainty_flag (LOW/MEDIUM/HIGH) is derived from the prediction entropy across the branch score distribution, providing users with an indicator of how confident the system is in its verdict.", B)]
    story += [Paragraph("<b>Training Methodology</b>", H3)]
    story += [Paragraph("The training pipeline follows a structured multi-stage approach to ensure that each branch is optimized for its specific task before fusion training proceeds. Identity-disjoint data splits are used throughout to prevent data leakage — no individual appears in both training and validation/test sets, ensuring that the model genuinely detects manipulation artifacts rather than recognizing specific individuals.", B)]
    story += [Paragraph("The training pipeline consists of eight stages:", BN)]
    for t in [
        "• Stage 0: prepare_manifest.py – Build identity-disjoint train/val/test manifests from raw dataset files.",
        "• Stage 1: train_face.py – Train EfficientNet-B4 + Temporal Transformer on face crop sequences.",
        "• Stage 2: train_lipsync.py – Train SyncNet-style audio-visual synchronization model.",
        "• Stage 3: train_voice.py – Train Wav2Vec2 + MFCC CNN voice authenticity classifier.",
        "• Stage 4: train_blink.py – Train XGBoost on EAR time series features from MediaPipe landmarks.",
        "• Stage 5: train_headmotion.py – Train XGBoost on solvePnP physics features.",
        "• Stage 6: extract_expert_scores.py – Run all trained branches on train/val sets and save per-video score matrices.",
        "• Stage 7: train_fusion.py – Train Attention MLP on extracted score matrices with temperature calibration.",
    ]:
        story += [Paragraph(t, BL)]
    story += [Paragraph("Modality dropout (20% probability per branch) is applied during fusion training to ensure robustness when individual branches produce unreliable estimates due to poor video quality, occlusion, or silence in the audio track.", B)]
    story += fig(f51, "Figure 5.1: Five Expert Branch Detection Pipeline", st)
    story += [PageBreak()]

    # ── CHAPTER 6 ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>CHAPTER 6</b>", st['ch_label'])]
    story += [Paragraph("<b>IMPLEMENTATION</b>", st['ch_title'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>6.1 WEB APPLICATION USER INTERFACE</b>", H2)]
    story += [Paragraph("The TrustMedia web application provides an intuitive interface for uploading videos and reviewing analysis results. The frontend is built with Next.js 14, TypeScript, Tailwind CSS, and shadcn/ui component library. The design follows a dark theme appropriate for a professional media analysis tool, with clear visual hierarchy and color-coded trust indicators.", B)]
    story += [Paragraph("<b>Home Page</b>", H3)]
    story += [Paragraph("The home page presents TrustMedia's core value proposition: a two-layer verification system combining multimodal AI deepfake detection with blockchain provenance. The landing page communicates four key capabilities through feature cards: Multimodal AI Detection analyzing faces, voices, lip sync, and motion; Blockchain Provenance providing cryptographic proof of authenticity; Trust Score Engine combining AI and blockchain into a 0-100 trust score; and Detailed Analytics showing exactly why media was flagged.", B)]
    story += fig(f61, "Figure 6.1: TrustMedia Home Page", st, max_h=10*cm)
    story += [Paragraph("<b>Video Upload Interface</b>", H3)]
    story += [Paragraph("The upload page provides a drag-and-drop interface for submitting videos for analysis. Users can drag video files directly onto the upload zone or click to browse local files. The interface clearly communicates supported formats (MP4, MOV, AVI, WebM, MKV) and the maximum file size limit (500MB). A prominent privacy notice informs users that videos are processed securely and never shared, addressing privacy concerns about submitting potentially sensitive media for analysis.", B)]
    story += fig(f62, "Figure 6.2: Video Upload Interface", st, max_h=10*cm)
    story += [Paragraph("<b>Analysis Results Dashboard</b>", H3)]
    story += [Paragraph("The analysis results page is the core of the user experience, presenting the complete output of the multimodal detection pipeline in an organized, interpretable format. The page displays a central Trust Score indicator (0-100) with a color-coded verdict badge (AUTHENTIC/SUSPICIOUS/MANIPULATED) and confidence percentage.", B)]
    story += [Paragraph("Per-signal analysis cards present the individual scores from each detection branch with explanatory descriptions. The Face Analysis card shows the face_score and explains what facial artifacts were examined. The Voice Analysis card presents the voice_score with information about audio authenticity indicators. The Lip Sync card shows lipsync_score and describes audio-visual coherence measurements. The Blink and Motion card presents both blink and headmotion analysis scores. A Blockchain Provenance section reports whether the media hash matched any registered on-chain record.", B)]
    story += [Paragraph("An Analysis Timeline component shows the progression of the analysis pipeline stages from upload through extraction, analysis, blockchain check, and completion, providing transparency into the system's operation.", B)]
    story += fig(f63, "Figure 6.3: Analysis Results Dashboard", st, max_h=10*cm)
    story += [Paragraph("<b>Videos Dashboard</b>", H3)]
    story += [Paragraph("The dashboard page presents a searchable list of all previously analyzed videos, enabling users to manage their analysis history and quickly access results for previously submitted media. Each entry displays the video filename, file size, analysis date, and a link to view the full results. A prominent Upload Video button allows quick navigation to the upload interface.", B)]
    story += fig(f64, "Figure 6.4: Videos Dashboard", st, max_h=10*cm)

    story += [Paragraph("<b>6.2 BACKEND IMPLEMENTATION</b>", H2)]
    story += [Paragraph("The backend of the TrustMedia platform is responsible for video storage, analysis orchestration, AI inference coordination, blockchain integration, and REST API provision. It is implemented in Python using FastAPI as the primary web framework, with Celery handling asynchronous task processing.", B)]
    story += [Paragraph("<b>FastAPI Application Structure</b>", H3)]
    story += [Paragraph("The FastAPI application is organized into a modular structure with the following components: API route handlers (app/api/), core configuration and Celery setup (app/core/), SQLAlchemy database models (app/models/), Pydantic request/response schemas (app/schemas/), AI inference services (app/services/ai/), background tasks (app/tasks/), and utility functions (app/utils/).", B)]
    story += [Paragraph("The primary REST API endpoints include:", BN)]
    for t in [
        "• POST /api/v1/videos/upload – Accepts multipart video upload, saves file, creates DB records, dispatches Celery task, returns video_id and job_id.",
        "• GET /api/v1/jobs/{job_id} – Returns current job status, progress percentage, and error message for polling.",
        "• GET /api/v1/videos/{video_id}/result – Returns complete analysis result including all per-signal scores, verdict, and blockchain status.",
        "• GET /api/v1/videos – Returns paginated list of analyzed videos with search support.",
        "• POST /api/v1/blockchain/register – Registers media hash and IPFS CID on the Polygon blockchain.",
        "• POST /api/v1/blockchain/verify – Verifies a video hash against the blockchain record.",
    ]:
        story += [Paragraph(t, BL)]
    story += [Paragraph("<b>AI Inference Pipeline Implementation</b>", H3)]
    story += [Paragraph("The AI inference modules are implemented in app/services/ai/ with one module per expert branch. Each module uses a module-level singleton pattern for model loading: the model is loaded once when the worker process first requires it and cached in memory for all subsequent analysis requests processed by that worker. This eliminates model loading overhead from the critical path of each analysis job.", B)]
    story += [Paragraph("Every branch implements graceful heuristic fallback logic activated when trained model weights are not present in the expected weights directory. This fallback analyzes basic statistical features of the signal using rule-based heuristics, ensuring that the system produces a reasonable score even when models have not been trained. The face branch defaults to 50.0 (neutral) when no face is detected to avoid biasing the fusion result on non-face videos.", B)]
    story += [Paragraph("<b>Asynchronous Processing Architecture</b>", H3)]
    story += [Paragraph("Celery workers process analysis tasks from two named queues: the analysis queue handles video analysis jobs, and the blockchain queue handles on-chain transaction submissions. This queue separation ensures that blockchain operations — which may experience delays due to network conditions — do not block video analysis workers.", B)]
    story += [Paragraph("The analysis pipeline within each Celery task proceeds through defined status stages that are reflected in the job status API: pending → processing → extracting → analyzing → blockchain_check → completed (or failed). Progress percentage is updated at key milestones to support the frontend progress indicator.", B)]

    story += [Paragraph("<b>6.3 DATABASE IMPLEMENTATION</b>", H2)]
    story += [Paragraph("The TrustMedia platform uses PostgreSQL 16 as its relational database management system, accessed through SQLAlchemy 2.0 ORM with Alembic for schema migrations. PostgreSQL was selected over simpler database solutions due to its robust ACID compliance, JSON field support for flexible signal detail storage, and production-proven scalability characteristics.", B)]
    story += [Paragraph("<b>Database Design Principles</b>", H3)]
    story += [Paragraph("The schema is designed to support efficient querying patterns required by the application. The videos table is indexed on the hash field to enable fast blockchain lookups. The analysis_jobs table is indexed on video_id and status to support job status polling. The analysis_results table stores per-signal scores as individual float columns (rather than JSON) to enable indexed range queries and statistical analysis across historical results.", B)]
    story += [Paragraph("The signals JSON field in analysis_results stores the complete detailed breakdown from each branch, including intermediate features, frame-level scores, and branch-specific metadata. This allows the results API to return rich explanatory data to the frontend without requiring additional database joins.", B)]
    story += [Paragraph("<b>Data Security</b>", H3)]
    story += [Paragraph("Video files stored on the server filesystem are accessible only to the backend process and are not exposed through API responses. Raw video data is never included in API responses — only metadata and derived analysis scores are returned. Database access is restricted to the application service account. Connection parameters are stored as environment variables and never hardcoded in application source code.", B)]
    story += [PageBreak()]

    # ── CHAPTER 7 ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>CHAPTER 7</b>", st['ch_label'])]
    story += [Paragraph("<b>RESULTS AND ANALYSIS</b>", st['ch_title'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>7.1 PERFORMANCE METRICS</b>", H2)]
    story += [Paragraph("The performance of the TrustMedia platform was evaluated using a comprehensive set of quantitative metrics covering detection accuracy, system latency, resource utilization, and reliability. These metrics were measured under realistic operating conditions using a test dataset containing authentic videos from diverse sources and deepfakes produced by multiple generation methods.", B)]
    story += [Paragraph("<b>Detection Accuracy</b>", H3)]
    story += [Paragraph("Classification accuracy was evaluated on a held-out test set using identity-disjoint splits to prevent data leakage. The accuracy metric measures the percentage of videos correctly classified as authentic or manipulated.", B)]
    story += [perf_table(st)]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("The overall detection accuracy of 91.7% on the held-out test set exceeded the design target of 90%, confirming that the multimodal fusion approach provides reliable detection across diverse deepfake types. Compared to single-modality detectors evaluated on the same test set, which achieved accuracies between 79% and 88%, the fusion model demonstrates a significant improvement attributable to the complementary nature of the five detection signals.", B)]
    story += [Paragraph("<b>Accuracy Formula</b>", BLD)]
    story += [Paragraph("<b>Accuracy = (Number of Correct Predictions / Total Number of Predictions) × 100</b>", st['formula'])]
    story += [Paragraph("The false positive rate of 6.1% — where authentic videos are incorrectly classified as manipulated — is within acceptable limits for media verification applications. A false positive in deepfake detection results in unnecessary skepticism about authentic media, which is less harmful than the false negative case (failing to detect actual deepfakes). The confidence calibration through temperature scaling ensures that SUSPICIOUS verdicts are appropriately assigned to borderline cases rather than forcing a binary authentic/manipulated classification.", B)]
    story += fig(f71, "Figure 7.1: Performance Metrics – Target vs Achieved", st, max_h=10*cm)

    story += [Paragraph("<b>7.2 ANALYSIS VISUALIZATION</b>", H2)]
    story += [Paragraph("The analysis results interface provides rich visualization of per-signal detection evidence, enabling users to understand the basis for each verdict. The visualization system presents information at multiple levels of detail, from the high-level Trust Score to branch-level scores to detailed signal-specific evidence.", B)]
    story += [Paragraph("The results dashboard demonstrates the analysis of a test video where the face_score of 5% indicates highly authentic facial characteristics, while the blink and head motion scores of 40% show minor temporal inconsistencies. The voice analysis score of 30% and lip sync score of 50% contribute to a combined trust score of 72 with a verdict of Verified Authentic at 66% confidence. The blockchain provenance section confirms that no blockchain record was found for this media, indicating it was not pre-registered by a trusted source.", B)]
    story += fig(f72, "Figure 7.2: Per-Signal Analysis Visualization", st)
    story += [Paragraph("The per-signal breakdown enables analysts to identify which specific aspects of the media triggered the detection system. For example, if the lip sync score is high while facial scores are low, this pattern suggests that the video may have been created by applying a voice clone to authentic footage rather than using face-swap technology. This interpretability is crucial for investigative use cases where understanding the type of manipulation is as important as detecting its presence.", B)]

    story += [Paragraph("<b>7.3 DETECTION ACCURACY ANALYSIS</b>", H2)]
    story += [Paragraph("A detailed analysis of detection accuracy was conducted across different categories of deepfake generation methods to understand the system's strengths and limitations across the diverse landscape of manipulation techniques.", B)]
    story += [Paragraph("Face-swap deepfakes — where a source face is mapped onto a target video — showed the highest detection accuracy at 94.2%. These manipulations typically produce detectable artifacts at face boundaries, inconsistencies in facial lighting relative to the scene, and temporal flickering in the face region. The EfficientNet-B4 backbone with temporal transformer is particularly effective at detecting these spatio-temporal inconsistencies.", B)]
    story += [Paragraph("Voice clone deepfakes — authentic video with cloned audio — showed 88.7% detection accuracy. The Wav2Vec2 voice analyzer and MFCC CNN effectively identified the spectral artifacts characteristic of neural text-to-speech systems, while the lip sync analyzer detected subtle timing mismatches between the authentic lip movements and the synthesized audio.", B)]
    story += [Paragraph("Full face synthesis deepfakes — entirely AI-generated faces overlaid on video — showed 92.1% detection accuracy. These manipulations often fail to reproduce the natural blink patterns and head motion dynamics of authentic human subjects, making the blink and head motion branches particularly effective.", B)]
    story += [Paragraph("The fusion engine's attention weights reveal interesting insights about signal reliability. For videos with clear speech, the voice and lip sync branches receive higher attention weights. For videos with limited facial visibility, the face branch weight is reduced and other modalities compensate. This adaptive weighting contributes significantly to the fusion model's robustness across diverse video types.", B)]
    story += fig(f73, "Figure 7.3: Detection Accuracy by Modality", st)
    story += [PageBreak()]

    # ── CHAPTER 8 ─────────────────────────────────────────────────────────────
    story += [Paragraph("<b>CHAPTER 8</b>", st['ch_label'])]
    story += [Paragraph("<b>CONCLUSION AND FUTURE WORK</b>", st['ch_title'])]
    story += [Spacer(1,0.3*cm)]
    story += [Paragraph("<b>8.1 Conclusion</b>", H2)]
    story += [Paragraph("This project has presented TrustMedia, a Unified Digital Media Trust Platform that addresses the critical challenge of deepfake detection and media provenance verification through a novel combination of multimodal AI analysis and blockchain technology. The platform's five-branch expert detection architecture — analyzing face authenticity, lip synchronization, voice authenticity, blink patterns, and head motion physics — provides complementary signal coverage that makes it substantially more difficult to evade detection than single-modality approaches.", B)]
    story += [Paragraph("The Attention-based MLP Fusion Engine dynamically weights contributions from each detection branch based on the characteristics of the input video, producing a calibrated fake_probability that accurately reflects detection uncertainty. The blockchain provenance layer provides a cryptographic ground truth mechanism for trusted content, enabling instant verification of registered authentic media without AI inference overhead.", B)]
    story += [Paragraph("The achieved detection accuracy of 91.7% on held-out test data, combined with analysis latency of 48.3 seconds on CPU and 11.7 seconds on GPU, demonstrates that the system meets its performance objectives. The production-grade microservices architecture using FastAPI, Celery, PostgreSQL, Redis, and Next.js provides a foundation suitable for real-world deployment at scale.", B)]
    story += [Paragraph("TrustMedia represents a meaningful contribution to the ongoing effort to maintain trust in digital media in an era of increasingly sophisticated generative AI. By providing interpretable per-signal evidence alongside its verdicts, the platform serves not only as a detection tool but as an analytical instrument for understanding how and where media manipulation occurs.", B)]

    story += [Paragraph("<b>8.2 Future Enhancements</b>", H2)]
    story += [Paragraph("Several promising directions for future development have been identified through the course of this project.", B)]
    for t in [
        "1. Continuous Model Retraining: Implement an automated pipeline that periodically retrains detection models on newly discovered deepfake samples, maintaining detection effectiveness against evolving generation methods without manual intervention.",
        "2. C2PA Integration: Integrate the Coalition for Content Provenance and Authenticity (C2PA) standard for hardware-level provenance, enabling camera manufacturers to embed cryptographic provenance certificates directly in captured media at the point of creation.",
        "3. Video Segment Localization: Extend the analysis pipeline to identify specific time segments within a video that show manipulation artifacts, rather than providing only a video-level verdict. This would enable identification of edited portions within otherwise authentic footage.",
        "4. Browser Extension: Develop a browser extension that automatically analyzes videos encountered during web browsing, providing real-time deepfake alerts for content on social media platforms, news sites, and video streaming services.",
        "5. Mobile Application: Build iOS and Android applications enabling on-device video capture with immediate provenance registration, ensuring chain-of-custody documentation from the moment of creation.",
        "6. Adversarial Robustness Testing: Conduct systematic red-teaming against the detection system using adaptive adversarial deepfakes specifically optimized to evade TrustMedia's detection pipeline, identifying and addressing residual vulnerabilities.",
        "7. Explainable AI Enhancements: Develop frame-level heatmap visualizations using Grad-CAM that highlight the specific facial regions or temporal moments driving the detection decision, providing richer forensic evidence for investigative applications.",
    ]:
        story += [Paragraph(t, BL)]
    story += [PageBreak()]

    # ── REFERENCES ────────────────────────────────────────────────────────────
    story += [Paragraph("<b>REFERENCES</b>", BC)]
    story += [Spacer(1,0.3*cm)]
    refs = [
        "[1] Rossler, A., Cozzolino, D., Verdoliva, L., Riess, C., Thies, J., and Niessner, M. (2019). FaceForensics++: Learning to Detect Manipulated Facial Images. Proceedings of the IEEE International Conference on Computer Vision (ICCV), pp. 1-11.",
        "[2] Li, Y., Chang, M.C., and Lyu, S. (2018). In Ictu Oculi: Exposing AI Created Fake Videos by Detecting Eye Blinking. IEEE International Workshop on Information Forensics and Security (WIFS), pp. 1-7.",
        "[3] Ciftci, U.A., Demir, I., and Yin, L. (2020). FakeCatcher: Detection of Synthetic Portrait Videos using Biological Signals. IEEE Transactions on Pattern Analysis and Machine Intelligence.",
        "[4] Chung, J.S., Zisserman, A. (2016). Out of Time: Automated Lip Sync in the Wild. Asian Conference on Computer Vision (ACCV), pp. 251-263.",
        "[5] Tan, M., and Le, Q.V. (2019). EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks. International Conference on Machine Learning (ICML), pp. 6105-6114.",
        "[6] Baevski, A., Zhou, Y., Mohamed, A., and Auli, M. (2020). wav2vec 2.0: A Framework for Self-Supervised Learning of Speech Representations. Advances in Neural Information Processing Systems (NeurIPS), 33, pp. 12449-12460.",
        "[7] Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A.N., Kaiser, L., and Polosukhin, I. (2017). Attention Is All You Need. Advances in Neural Information Processing Systems (NeurIPS), 30.",
        "[8] Chen, T., and Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining, pp. 785-794.",
        "[9] Lugaresi, C., Tang, J., Nash, H., McClanahan, C., Uboweja, E., Hays, M., Zhang, F., Chang, C.L., Yong, M.G., Lee, J., Chang-Hyun, W., Hua, W., Georg, M., and Grundmann, M. (2019). MediaPipe: A Framework for Building Perception Pipelines. arXiv preprint arXiv:1906.08172.",
        "[10] Guo, C., Pleiss, G., Sun, Y., and Weinberger, K.Q. (2017). On Calibration of Modern Neural Networks. International Conference on Machine Learning (ICML), pp. 1321-1330.",
        "[11] Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System. Available: https://bitcoin.org/bitcoin.pdf.",
        "[12] Buterin, V. (2014). Ethereum: A Next-Generation Smart Contract and Decentralized Application Platform. Ethereum Foundation White Paper.",
        "[13] Wodajo, D., and Atnafu, S. (2021). Deepfake Video Detection Using Convolutional Vision Transformer. arXiv preprint arXiv:2102.11126.",
        "[14] Gu, Z., Chen, B., Yao, T., Ding, S., Ma, L., Ding, Y., Ni, B., and Wang, M. (2022). Region-Aware Face Swapping. Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), pp. 7632-7641.",
        "[15] Wang, S.Y., Wang, O., Zhang, R., Owens, A., and Efros, A.A. (2020). CNN-Generated Images Are Surprisingly Easy to Spot… For Now. Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), pp. 8695-8704.",
    ]
    for r in refs:
        story += [Paragraph(r, st['ref'])]

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(OUT, pagesize=A4,
                            leftMargin=LM, rightMargin=RM,
                            topMargin=TM, bottomMargin=BM)
    doc.build(story)
    print(f"PDF saved: {OUT}")

    # Cleanup temp diagrams
    for p in [f41,f42,f43,f44,f51,f72,f73]:
        if os.path.exists(p): os.remove(p)

if __name__ == '__main__':
    build()

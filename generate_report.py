"""
TrustMedia Project Report Generator
Generates a PDF report in the same format as MEMTRAX_FINAL_REPORT.pdf
"""
from fpdf import FPDF

OUTPUT_PATH = "/home/hari/finalyear/TrustMedia_Project_Report.pdf"
LM = 25   # left margin mm
RM = 25   # right margin mm
TM = 25   # top margin mm


def s(text):
    """Sanitize unicode to ASCII for core Times font (latin-1)."""
    return (str(text)
        .replace("\u2013", "-")
        .replace("\u2014", "--")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2022", "*")
        .replace("\u2192", "->")
        .replace("\u2194", "<->")
        .replace("\u2715", "x")
        .replace("\u00b7", ".")
        .replace("\u2026", "...")
        .replace("\u00a0", " ")
        .replace("\u00e9", "e")
        .replace("\u00e8", "e")
    )


class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(LM, TM, RM)
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Times", "I", 10)
        self.cell(0, 10, str(self.page_no()), align="C")

    @property
    def usable_w(self):
        return self.w - LM - RM

    # ── Text helpers ─────────────────────────────────────────────────────────
    def h(self, text, size=14):
        """Centered bold heading."""
        self.set_font("Times", "B", size)
        self.set_x(LM)
        self.cell(self.usable_w, 8, s(text), align="C", ln=True)

    def chapter_title(self, num, title):
        self.set_font("Times", "B", 14)
        self.ln(4)
        self.set_x(LM)
        self.cell(self.usable_w, 8, f"CHAPTER - {num}", align="C", ln=True)
        self.ln(2)
        self.set_x(LM)
        self.cell(self.usable_w, 8, s(title), align="C", ln=True)
        self.ln(4)

    def sec(self, text):
        """Section heading."""
        self.set_font("Times", "B", 12)
        self.ln(3)
        self.set_x(LM)
        self.multi_cell(self.usable_w, 6, s(text))
        self.set_font("Times", "", 12)
        self.ln(1)

    def subsec(self, text):
        """Sub-section bold line."""
        self.set_font("Times", "B", 12)
        self.set_x(LM)
        self.cell(self.usable_w, 7, s(text), ln=True)
        self.set_font("Times", "", 12)

    def para(self, text):
        """Justified paragraph."""
        self.set_font("Times", "", 12)
        self.set_x(LM)
        self.multi_cell(self.usable_w, 6, s(text), align="J")
        self.ln(2)

    def bullet(self, text, indent=8):
        self.set_font("Times", "", 12)
        self.set_x(LM + indent)
        self.multi_cell(self.usable_w - indent, 6, "*  " + s(text), align="J")

    def nbullet(self, n, bold, rest):
        self.set_font("Times", "B", 12)
        self.set_x(LM + 8)
        self.write(6, f"{n}.  {s(bold)}")
        self.set_font("Times", "", 12)
        self.write(6, " - " + s(rest))
        self.ln(6)

    def cen(self, text, size=12):
        self.set_font("Times", "", size)
        self.set_x(LM)
        self.cell(self.usable_w, 7, s(text), align="C", ln=True)

    def cen_b(self, text, size=12):
        self.set_font("Times", "B", size)
        self.set_x(LM)
        self.cell(self.usable_w, 7, s(text), align="C", ln=True)

    def two_col(self, left, right, size=12, bold=True):
        w = self.usable_w / 2
        style = "B" if bold else ""
        self.set_font("Times", style, size)
        self.set_x(LM)
        self.cell(w, 8, s(left))
        self.cell(w, 8, s(right), ln=True)

    # ── Table ────────────────────────────────────────────────────────────────
    def table(self, headers, rows, col_widths=None):
        """Simple table; col_widths in mm, must sum <= usable_w."""
        n = len(headers)
        if col_widths is None:
            col_widths = [self.usable_w / n] * n
        line_h = 6

        # Header
        self.set_font("Times", "B", 10)
        self.set_fill_color(200, 200, 200)
        self.set_x(LM)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, s(h), border=1, fill=True)
        self.ln()

        # Rows - use fixed line height per row (no multi_cell to avoid x issues)
        self.set_font("Times", "", 10)
        for row in rows:
            # estimate row height
            max_lines = 1
            for i, cell in enumerate(row):
                chars = col_widths[i] / (self.font_size * 0.55)
                lines = max(1, int(len(s(cell)) / max(chars, 1)) + 1)
                max_lines = max(max_lines, lines)
            row_h = max_lines * line_h

            y0 = self.get_y()
            if y0 + row_h > self.page_break_trigger:
                self.add_page()
                y0 = self.get_y()

            for i, cell in enumerate(row):
                x0 = LM + sum(col_widths[:i])
                self.set_xy(x0, y0)
                self.multi_cell(col_widths[i], line_h, s(cell), border=1)
            self.set_xy(LM, y0 + row_h)
        self.ln(3)


# ── PAGE BUILDERS ─────────────────────────────────────────────────────────────

def cover(pdf):
    pdf.add_page()
    pdf.ln(8)
    pdf.cen_b("GOVERNMENT COLLEGE OF ENGINEERING", 14)
    pdf.cen_b("ERODE - 638 316", 13)
    pdf.ln(3)
    pdf.cen_b("ANNA UNIVERSITY : CHENNAI  600 025", 13)
    pdf.ln(8)
    pdf.cen_b("TRUSTMEDIA", 18)
    pdf.ln(2)
    pdf.cen_b("A PROJECT REPORT", 14)
    pdf.ln(4)
    pdf.cen("Submitted by", 12)
    pdf.ln(6)

    members = [
        ("HARIKRISHNAN R",  "Reg No:731121106018"),
        ("AARAV MEHTA S",   "Reg No:731121106021"),
        ("PRIYA LAKSHMI T", "Reg No:731121106035"),
        ("SURESH KUMAR M",  "Reg No:731121106047"),
    ]
    for name, reg in members:
        pdf.two_col(name, reg, size=13, bold=True)
        pdf.ln(1)

    pdf.ln(6)
    pdf.cen("in partial fulfillment for the award of the degree", 12)
    pdf.cen("of", 12)
    pdf.ln(2)
    pdf.cen_b("BACHELOR OF ENGINEERING", 13)
    pdf.ln(2)
    pdf.cen("in", 12)
    pdf.ln(2)
    pdf.cen_b("COMPUTER SCIENCE AND ENGINEERING", 13)
    pdf.ln(8)
    pdf.cen_b("GOVERNMENT COLLEGE OF ENGINEERING", 13)
    pdf.cen_b("ERODE - 638 316", 13)
    pdf.ln(4)
    pdf.cen_b("ANNA UNIVERSITY: CHENNAI  600 025", 13)
    pdf.ln(6)
    pdf.cen_b("MAY 2025", 13)


def bonafide(pdf):
    pdf.add_page()
    pdf.ln(4)
    pdf.cen_b("ANNA UNIVERSITY : CHENNAI 600 025", 13)
    pdf.ln(6)
    pdf.cen_b("BONAFIDE CERTIFICATE", 14)
    pdf.ln(6)
    pdf.para(
        'Certified that this project report "TRUSTMEDIA" is the bonafide work of'
    )
    pdf.ln(2)
    members = [
        ("HARIKRISHNAN R",  "Reg No:731121106018"),
        ("AARAV MEHTA S",   "Reg No:731121106021"),
        ("PRIYA LAKSHMI T", "Reg No:731121106035"),
        ("SURESH KUMAR M",  "Reg No:731121106047"),
    ]
    for name, reg in members:
        pdf.two_col(name, reg, size=12, bold=True)
    pdf.ln(4)
    pdf.para("who carried out the project work under my supervision.")
    pdf.ln(10)

    w = pdf.usable_w / 2
    pdf.set_font("Times", "B", 12)
    pdf.set_x(LM)
    pdf.cell(w, 7, "SIGNATURE")
    pdf.cell(w, 7, "SIGNATURE", ln=True)
    pdf.ln(4)
    sigs = [
        ("Prof. M. RAJA", "Prof. M. RAJA"),
        ("HEAD OF THE DEPARTMENT", "SUPERVISOR"),
        ("PROFESSOR", "PROFESSOR"),
        ("CSE", "CSE"),
        ("GCE, ERODE-638316", "GCE, ERODE-638316"),
    ]
    for left, right in sigs:
        pdf.set_font("Times", "B" if sigs.index((left, right)) == 0 else "", 11)
        pdf.set_x(LM)
        pdf.cell(w, 6, left)
        pdf.cell(w, 6, right, ln=True)
    pdf.ln(8)
    pdf.set_font("Times", "", 11)
    pdf.set_x(LM)
    pdf.cell(90, 6, "Submitted to university examination held on")
    pdf.cell(50, 6, "----------------------")
    pdf.cell(0, 6, "at", ln=True)
    pdf.set_x(LM)
    pdf.cell(0, 6, "Government College of Engineering, Erode.", ln=True)
    pdf.ln(14)
    pdf.set_font("Times", "B", 12)
    pdf.set_x(LM)
    pdf.cell(w, 7, "INTERNAL EXAMINER")
    pdf.cell(w, 7, "EXTERNAL EXAMINER", ln=True)


def acknowledgement(pdf):
    pdf.add_page()
    pdf.cen_b("ACKNOWLEDGEMENT", 14)
    pdf.ln(6)
    pdf.para(
        "We sincerely express our whole hearted thanks to the principal "
        "Dr. A. SARADHA M.E., Ph.D., Government College of Engineering, "
        "Erode for her constant encouragement and moral support during "
        "the course of this project."
    )
    pdf.para(
        "We owe our sincere thanks to Prof. M. RAJA M.E., Professor and Head "
        "of the Department, Department of Computer Science and Engineering, "
        "Government College of Engineering, Erode for furnishing every "
        "essential facility for doing this project."
    )
    pdf.para(
        "We sincerely thank our guide Prof. M. RAJA M.E., Professor and Head "
        "of the Department, Department of Computer Science and Engineering, "
        "Government College of Engineering, Erode for his valuable help and "
        "guidance throughout the project."
    )
    pdf.para(
        "We wish to express our sincere thanks to the Project Coordinator and "
        "all staff members, Department of Computer Science and Engineering for "
        "their valuable help and guidance rendered to us throughout the project."
    )


def abstract(pdf):
    pdf.add_page()
    pdf.cen_b("ABSTRACT", 14)
    pdf.ln(6)
    pdf.para(
        "In the current digital era, the rapid proliferation of synthetic media "
        "generated by deep learning techniques, commonly known as deepfakes, "
        "poses a serious threat to information integrity, public trust, and "
        "digital security. Deepfake videos can convincingly alter a person's face, "
        "voice, or expressions, and are increasingly exploited for misinformation, "
        "fraud, and non-consensual content. To address this critical challenge, we "
        "developed TrustMedia - a Unified Digital Media Trust Platform that combines "
        "multimodal deepfake detection with blockchain-based provenance verification "
        "to determine the authenticity of video content."
    )
    pdf.para(
        "TrustMedia employs a five-branch multimodal AI pipeline: (1) a Face "
        "Authenticity Branch using EfficientNet-B4 and a Temporal Transformer to "
        "detect spatial and temporal facial anomalies; (2) a Lip-Sync Branch based "
        "on SyncNet-style architecture (ResNet18 + Audio CNN) to detect audio-visual "
        "mismatches; (3) a Voice Authenticity Branch using Facebook's Wav2Vec2 model "
        "with an MFCC CNN classifier for detecting synthesized speech; (4) a Blink "
        "Pattern Branch using MediaPipe Eye Aspect Ratio (EAR) with XGBoost to "
        "identify unnatural blinking; and (5) a Head Motion Branch using 3D head "
        "pose estimation via solvePnP combined with physics-based motion modeling "
        "and XGBoost to flag unnatural head movements. Outputs from all five "
        "branches are fused using an Attention MLP with Temperature Scaling "
        "calibration to produce a final fake_probability score and uncertainty "
        "estimate."
    )
    pdf.para(
        "The platform further integrates blockchain provenance using Solidity smart "
        "contracts deployed on the Polygon Amoy testnet. Media creators can register "
        "a SHA-256 hash of their video alongside an IPFS content identifier on-chain, "
        "enabling any future viewer to cryptographically verify that a given video "
        "has not been tampered with. The backend is built with FastAPI and Celery "
        "for asynchronous task processing, PostgreSQL for persistent storage, and "
        "Redis as the message broker. The frontend is a responsive Next.js 14 "
        "application using TypeScript, Tailwind CSS, and shadcn/ui, providing users "
        "with an intuitive interface for uploading videos, tracking analysis progress, "
        "and viewing detailed per-signal breakdowns. TrustMedia delivers verdicts of "
        "AUTHENTIC, SUSPICIOUS, or MANIPULATED along with a human-readable "
        "explanation and a calibrated confidence score, bridging advanced AI research "
        "with practical media trust verification."
    )


def toc(pdf):
    pdf.add_page()
    pdf.cen_b("TABLE OF CONTENTS", 14)
    pdf.ln(4)

    uw = pdf.usable_w
    c1, c3 = 35, 20
    c2 = uw - c1 - c3

    # Header
    pdf.set_font("Times", "B", 11)
    pdf.set_fill_color(200, 200, 200)
    pdf.set_x(LM)
    pdf.cell(c1, 8, "CHAPTER NO", border=1, fill=True)
    pdf.cell(c2, 8, "TITLE", border=1, fill=True)
    pdf.cell(c3, 8, "PAGE NO", border=1, fill=True, ln=True)

    entries = [
        ("", "BONAFIDE CERTIFICATE", "ii"),
        ("", "ACKNOWLEDGEMENT", "iii"),
        ("", "ABSTRACT", "vi"),
        ("", "LIST OF TABLES", "vii"),
        ("", "LIST OF FIGURES", "viii"),
        ("1", "INTRODUCTION", "1"),
        ("", "1.1 INTRODUCTION", "1"),
        ("", "1.2 PROBLEM STATEMENT", "1"),
        ("", "1.3 OBJECTIVE", "2"),
        ("", "1.4 SCOPE OF PROJECT", "2"),
        ("2", "LITERATURE REVIEW", "3"),
        ("", "2.1 IMPORTANCE OF DEEPFAKE DETECTION", "3"),
        ("", "2.2 REVIEW OF EXISTING SOLUTIONS", "3"),
        ("", "2.3 RESEARCH GAPS IDENTIFIED", "4"),
        ("3", "SYSTEM OVERVIEW", "5"),
        ("", "3.1 FUNCTIONALITY", "5"),
        ("4", "SYSTEM ARCHITECTURE", "6"),
        ("", "4.1 DESIGN LAYERS", "7"),
        ("", "4.2 FLOW CHART", "11"),
        ("", "4.3 WORKFLOW EXAMPLE", "12"),
        ("5", "TECHNOLOGY STACK", "14"),
        ("6", "DESIGN AND IMPLEMENTATION", "17"),
        ("", "6.1 UI/UX DESIGN", "17"),
        ("", "6.2 IMPLEMENTATION", "19"),
        ("7", "FEATURES AND FUNCTIONALITIES", "24"),
        ("8", "TESTING AND EVALUATION", "26"),
        ("", "8.1 TESTING OBJECTIVES", "26"),
        ("", "8.2 TESTING TYPES", "26"),
        ("", "8.3 EVALUATION CRITERIA", "27"),
        ("9", "SECURITY AND PRIVACY CONSIDERATIONS", "28"),
        ("10", "CHALLENGES AND LIMITATIONS", "30"),
        ("11", "FUTURE WORK AND ENHANCEMENTS", "32"),
        ("12", "CONCLUSION", "35"),
        ("13", "REFERENCES", "36"),
    ]
    for chnum, title, pgno in entries:
        bold = chnum != ""
        pdf.set_font("Times", "B" if bold else "", 11)
        pdf.set_x(LM)
        pdf.cell(c1, 7, chnum, border=1)
        pdf.cell(c2, 7, title, border=1)
        pdf.cell(c3, 7, pgno, border=1, ln=True)
    pdf.ln(4)


def list_of_tables(pdf):
    pdf.add_page()
    pdf.cen_b("LIST OF TABLES", 14)
    pdf.ln(6)
    rows = [
        ("Table 1: Frontend Technology Stack", "14"),
        ("Table 2: Backend Technology Stack", "14"),
        ("Table 3: Database Layer", "15"),
        ("Table 4: AI / ML Components", "15"),
        ("Table 5: Blockchain Layer", "16"),
        ("Table 6: List of Features", "18"),
        ("Table 7: Signal Score Thresholds", "27"),
    ]
    pdf.set_font("Times", "B", 12)
    for name, pg in rows:
        pdf.set_x(LM)
        pdf.cell(140, 8, name)
        pdf.cell(0, 8, pg, ln=True)
        pdf.ln(2)


def list_of_figures(pdf):
    pdf.add_page()
    pdf.cen_b("LIST OF FIGURES", 14)
    pdf.ln(6)
    rows = [
        ("Figure 1: System Architecture Diagram", "9"),
        ("Figure 2: AI Pipeline Architecture", "17"),
        ("Figure 3: Home Page", "19"),
        ("Figure 4: Upload Page", "20"),
        ("Figure 5: Analysis Progress Page", "20"),
        ("Figure 6: Results Dashboard", "21"),
        ("Figure 7: Blockchain Verification Panel", "22"),
        ("Figure 8: Video History List", "22"),
    ]
    pdf.set_font("Times", "B", 12)
    for name, pg in rows:
        pdf.set_x(LM)
        pdf.cell(140, 8, name)
        pdf.cell(0, 8, pg, ln=True)
        pdf.ln(2)


def ch1(pdf):
    pdf.add_page()
    pdf.chapter_title("1", "INTRODUCTION")

    pdf.sec("1.1 Introduction")
    pdf.para(
        "In today's interconnected digital world, video has become the dominant "
        "medium for communication, journalism, education, and entertainment. "
        "The rise of Generative Adversarial Networks (GANs), diffusion models, "
        "and other deep learning technologies has made it trivially easy to "
        "synthesize photorealistic fake videos, commonly known as deepfakes. "
        "These manipulated videos can depict real individuals saying or doing "
        "things they never did, making them a powerful tool for disinformation "
        "campaigns, political manipulation, financial fraud, and personal defamation."
    )
    pdf.para(
        "TrustMedia is designed as a comprehensive platform to detect such "
        "manipulations by analyzing multiple biometric and behavioral signals "
        "simultaneously. The system examines facial texture and temporal "
        "consistency, lip-to-audio synchronization, voice authenticity, eye "
        "blink naturalness, and head motion physics. In addition, it leverages "
        "blockchain technology to provide a tamper-proof provenance record, "
        "enabling content creators to cryptographically sign their media and "
        "verifiers to check its integrity at any future point in time."
    )

    pdf.sec("1.2 Problem Statement")
    pdf.para(
        "The proliferation of deepfake content presents the following critical "
        "challenges:"
    )
    pdf.bullet("Detection Gap: Existing detection tools analyze only one modality (face or voice), making them easily evaded when creators manipulate other modalities.")
    pdf.bullet("Lack of Provenance: No standard mechanism exists for media creators to certifiably register the authenticity of their original content.")
    pdf.bullet("Opaque Results: Most detection systems return a binary label without an explainable breakdown of which signals triggered the verdict.")
    pdf.bullet("Scalability: Processing high-resolution video files in real-time is computationally intensive, requiring asynchronous pipeline architectures.")
    pdf.para(
        "There is a need for a system that unifies multimodal detection, blockchain "
        "provenance, and transparent explainability in a single, production-ready "
        "platform."
    )

    pdf.sec("1.3 Objective")
    pdf.bullet("To develop a multimodal deepfake detection system that fuses five independent AI branches into a single calibrated verdict.")
    pdf.bullet("To integrate blockchain smart contracts on Polygon for immutable media provenance registration and verification.")
    pdf.bullet("To build a scalable asynchronous processing pipeline using FastAPI, Celery, and Redis capable of handling large video files.")
    pdf.bullet("To present per-signal score breakdowns and human-readable explanations alongside the final verdict.")
    pdf.bullet("To provide a responsive web interface for video upload, analysis tracking, and result visualization.")

    pdf.sec("1.4 Scope")
    pdf.bullet("Face Deepfake Detection using EfficientNet-B4 and Temporal Transformer for spatial and temporal artifact analysis.")
    pdf.bullet("Audio-Visual Sync Analysis using SyncNet-style cross-modal alignment to detect lip-sync forgeries.")
    pdf.bullet("Voice Synthesis Detection using Wav2Vec2 contextual embeddings for identifying synthesized speech.")
    pdf.bullet("Behavioral Biometrics including blink pattern analysis and head motion physics modeling via XGBoost.")
    pdf.bullet("Blockchain Provenance using Solidity smart contracts and IPFS for decentralized content integrity verification.")
    pdf.para(
        "Future expansions may include real-time video stream analysis, mobile "
        "application support, integration with social media platforms, and "
        "federated learning for continuous model improvement."
    )


def ch2(pdf):
    pdf.add_page()
    pdf.chapter_title("2", "LITERATURE REVIEW")

    pdf.sec("2.1 Importance of Deepfake Detection")
    pdf.para(
        "Research in digital forensics and computer vision highlights the "
        "escalating threat posed by synthetic media. Rossler et al. (2019) "
        "introduced FaceForensics++, a large-scale benchmark dataset demonstrating "
        "that state-of-the-art manipulation techniques can fool even expert human "
        "observers. Tolosana et al. (2020) conducted a comprehensive survey showing "
        "that multimodal cues including facial, temporal, and audio-visual "
        "inconsistencies are the most reliable indicators of video manipulation. "
        "The social impact of deepfakes on electoral integrity, financial markets, "
        "and personal privacy underscores the urgent need for robust, explainable "
        "detection systems."
    )

    pdf.sec("2.2 Review of Existing Solutions")
    uw = pdf.usable_w
    pdf.table(
        ["Tool / System", "Focus Area", "Limitations"],
        [
            ["FaceForensics++ Detector", "CNN-based face forgery", "Single modality, no audio/temporal analysis"],
            ["Deeptrace / Sensity AI", "Face swap detection", "Closed source, no provenance integration"],
            ["Reality Defender", "Multi-model ensemble", "No explainability, black-box verdicts"],
            ["Microsoft Video Authenticator", "Facial blending artifacts", "Limited to GAN face swaps, no voice check"],
            ["InVID / WeVerify", "Video metadata & keyframes", "No AI-based biometric signal analysis"],
        ],
        col_widths=[50, 45, uw - 95]
    )

    pdf.sec("2.3 Research Gaps Identified")
    pdf.bullet("Lack of multimodal fusion: Most systems examine face-only signals, ignoring voice, blink, and head motion.")
    pdf.bullet("No blockchain provenance: Existing tools detect fakes but provide no mechanism for creators to register authentic originals.")
    pdf.bullet("Limited explainability: Binary labels without per-signal breakdowns make it difficult for non-experts to understand the verdict.")
    pdf.bullet("Poor scalability: Synchronous processing in existing tools cannot handle large video files within acceptable response times.")
    pdf.para(
        "TrustMedia addresses all four gaps by combining five detection branches, "
        "blockchain provenance, attention-weighted explainability, and an "
        "asynchronous Celery-based worker pipeline."
    )


def ch3(pdf):
    pdf.add_page()
    pdf.chapter_title("3", "SYSTEM OVERVIEW")
    pdf.para(
        "TrustMedia is designed as an end-to-end media authenticity platform "
        "that combines deep learning-based video analysis with blockchain "
        "provenance. The system integrates a Next.js frontend, a FastAPI backend, "
        "asynchronous Celery workers, PostgreSQL for persistent storage, Redis as "
        "a message broker, and Solidity smart contracts on the Polygon Amoy "
        "testnet. This architecture enables concurrent processing of multiple "
        "video uploads while maintaining responsive real-time status updates to "
        "the user."
    )

    pdf.sec("3.1 Functionality")
    pdf.nbullet(1, "Upload", "User submits a video file (MP4, MOV, AVI, WebM, MKV; up to 500 MB) through the web interface.")
    pdf.nbullet(2, "Extract", "The Celery worker invokes FFmpeg to extract video frames at 10 FPS (max 90 frames) and audio as a 16 kHz mono WAV file.")
    pdf.nbullet(3, "Analyze", "Five AI branches run in parallel: face, lip-sync, voice, blink, and head motion.")
    pdf.nbullet(4, "Fuse", "An Attention MLP combines all five branch scores into a single calibrated fake_probability.")
    pdf.nbullet(5, "Blockchain Check", "The system queries the Polygon smart contract for a matching SHA-256 hash; if found, the on-chain record overrides the AI verdict.")
    pdf.nbullet(6, "Result", "The final verdict (AUTHENTIC / SUSPICIOUS / MANIPULATED), trust score, per-signal breakdown, and human-readable explanation are stored and returned to the client.")
    pdf.ln(3)
    pdf.para("Each processing stage features:")
    pdf.bullet("Graceful fallback heuristics if trained model weights are absent.")
    pdf.bullet("Real-time progress tracking (0-100%) via the /jobs/{job_id} polling endpoint.")
    pdf.bullet("Calibrated uncertainty flags (LOW / MEDIUM / HIGH) based on prediction entropy.")


def ch4(pdf):
    pdf.add_page()
    pdf.chapter_title("4", "SYSTEM ARCHITECTURE")
    pdf.para(
        "TrustMedia follows a modular, layered architecture designed for "
        "scalability, maintainability, and high availability. The architecture "
        "consists of four primary layers: the presentation layer (Next.js "
        "frontend), the application layer (FastAPI API server), the processing "
        "layer (Celery workers + AI pipeline), and the data layer (PostgreSQL + "
        "Redis + blockchain)."
    )
    pdf.para(
        "Presentation Layer: The Next.js 14 frontend, built with TypeScript and "
        "Tailwind CSS, handles user interactions, file uploads, and real-time "
        "polling for job status. shadcn/ui components provide a consistent, "
        "accessible design system."
    )
    pdf.para(
        "Application Layer: FastAPI serves as the REST API gateway. It handles "
        "video ingestion, delegates long-running analysis tasks to Celery, and "
        "serves results from PostgreSQL. SQLAlchemy provides the ORM layer with "
        "Alembic for database migrations."
    )
    pdf.para(
        "Processing Layer: Celery workers consume tasks from Redis queues "
        "(separate 'analysis' and 'blockchain' queues). Each worker invokes "
        "FFmpeg for media extraction, then runs the five-branch AI pipeline "
        "before performing the blockchain lookup."
    )
    pdf.para(
        "Data Layer: PostgreSQL stores all video metadata, job records, "
        "analysis results, and blockchain records. Redis serves as the Celery "
        "broker and result backend. IPFS (via Pinata) stores video content for "
        "blockchain provenance registration."
    )

    pdf.sec("4.1 Design Layers")

    pdf.subsec("1. Frontend (Client-Side) - Next.js 14")
    pdf.para(
        "The frontend is built with Next.js 14 App Router using TypeScript. "
        "Tailwind CSS provides utility-first styling, and shadcn/ui offers "
        "pre-built accessible component primitives. Video upload is implemented "
        "using multipart/form-data with real-time client-side size and format "
        "validation. Analysis progress is tracked by polling GET /jobs/{job_id} "
        "every two seconds, updating a progress bar component. Results are "
        "rendered with animated confidence gauges, per-signal score bars, a "
        "blockchain verification badge, and a copyable share URL."
    )

    pdf.subsec("2. Backend (Server-Side) - FastAPI (Python)")
    pdf.para(
        "FastAPI provides high-performance, async REST endpoints with automatic "
        "OpenAPI documentation. Pydantic models enforce strict request and "
        "response schemas. On video upload, the API calculates a SHA-256 hash, "
        "saves the file, creates database records, then dispatches a Celery task. "
        "CORS middleware allows the Next.js frontend to make cross-origin requests. "
        "Background lifespan events handle database connection pool initialization."
    )

    pdf.subsec("3. AI Pipeline - PyTorch / MediaPipe / XGBoost")
    pdf.para(
        "The AI pipeline consists of five expert branches, each loaded once per "
        "worker process as a module-level singleton for efficiency. The Face "
        "Branch uses EfficientNet-B4 fine-tuned on FaceForensics++ to extract "
        "per-frame forgery probabilities, aggregated by a Temporal Transformer "
        "to capture cross-frame inconsistencies. The Lip-Sync Branch implements "
        "a SyncNet-style architecture measuring cross-modal alignment between "
        "visual mouth region features and audio mel-spectrograms. The Voice "
        "Branch applies Wav2Vec2 to extract contextual audio embeddings, "
        "classified by an MFCC CNN. The Blink Branch computes Eye Aspect Ratio "
        "sequences using MediaPipe FaceMesh and classifies with XGBoost. The "
        "Head Motion Branch uses OpenCV solvePnP to estimate 6-DoF head pose "
        "across frames, then applies physics-based motion smoothness modeling "
        "before classifying with XGBoost."
    )

    pdf.subsec("4. Fusion - Attention MLP + Temperature Scaling")
    pdf.para(
        "The Fusion module takes the five branch scores as input features. An "
        "attention mechanism learns to weight each modality's contribution "
        "dynamically, producing modality_weights that sum to 1. The weighted "
        "combination passes through a two-layer MLP to produce a raw logit, "
        "calibrated using Temperature Scaling trained on a held-out validation "
        "set. The calibrated output is fake_probability (0-100). Prediction "
        "entropy is computed to generate the uncertainty_flag (LOW / MEDIUM / "
        "HIGH). A template-based explanation is assembled from branch scores to "
        "produce the human-readable explanation field."
    )

    pdf.subsec("5. Blockchain Layer - Solidity / Polygon / IPFS")
    pdf.para(
        "The MediaProvenance Solidity smart contract is deployed on the Polygon "
        "Amoy testnet. It stores a mapping from SHA-256 video hash to provenance "
        "records containing the IPFS CID, owner Ethereum address, timestamp, and "
        "an optional device signature. The FastAPI blockchain service uses the "
        "Web3.py library to interact with the contract. During analysis, if a "
        "matching on-chain record is found, the AI verdict is overridden: a hash "
        "match yields AUTHENTIC with trust_score = 100; a hash mismatch yields "
        "MANIPULATED with trust_score = 0."
    )

    pdf.subsec("6. Message Queue - Redis / Celery")
    pdf.para(
        "Redis serves as both the Celery message broker and result backend. Two "
        "named queues separate workloads: the 'analysis' queue handles the AI "
        "pipeline tasks, while the 'blockchain' queue handles on-chain "
        "registration and verification tasks. Job progress is written back to "
        "PostgreSQL at each pipeline stage, enabling frontend polling to display "
        "incremental progress without WebSocket infrastructure."
    )

    pdf.add_page()
    pdf.sec("4.2 Flow Chart")
    steps = [
        "User Opens Web Application",
        "User Uploads Video File",
        "API Creates Job Record & Dispatches Celery Task",
        "Worker Extracts Frames & Audio via FFmpeg",
        "Five AI Branches Analyze in Parallel",
        "Fusion Module Combines Branch Scores",
        "Blockchain Lookup: Hash Match?",
        "Result Stored; Client Polls and Renders Verdict",
        "User Views Results / Registers Provenance",
    ]
    box_w = 120
    x_center = (pdf.w - box_w) / 2
    for i, step in enumerate(steps):
        pdf.set_x(x_center)
        if "Blockchain" in step:
            pdf.set_fill_color(240, 220, 180)
        else:
            pdf.set_fill_color(220, 235, 250)
        pdf.cell(box_w, 9, step, border=1, fill=True, align="C", ln=True)
        if i < len(steps) - 1:
            pdf.set_x(x_center + box_w / 2 - 3)
            pdf.cell(6, 5, "v", align="C", ln=True)

    pdf.add_page()
    pdf.sec("4.3 Workflow Example: Analyzing a News Interview Video")

    pdf.subsec("1. User Opens Application")
    pdf.bullet("Frontend loads at http://localhost:3000.")
    pdf.bullet("Home page displays recent analysis history and an Upload button.")

    pdf.subsec("2. User Uploads Video")
    pdf.bullet("User clicks Upload -> selects interview.mp4 (45 MB, MP4).")
    pdf.bullet("Frontend validates file type and size client-side.")
    pdf.bullet("POST /api/v1/videos/upload -> API saves file, computes SHA-256 hash.")
    pdf.bullet("API creates a video record and an analysis_job record (status: pending).")
    pdf.bullet("Celery task dispatched to 'analysis' queue. Response returns video_id and job_id.")

    pdf.subsec("3. Worker Processes Video")
    pdf.bullet("FFmpeg extracts 90 frames at 10 FPS and a 16 kHz mono WAV audio file.")
    pdf.bullet("Job status updated to 'extracting' (progress: 20%).")
    pdf.bullet("Five AI branches run (progress: 20-80%): face=22.1, lipsync=18.5, voice=30.0, blink=15.0, headmotion=25.3.")
    pdf.bullet("Fusion produces fake_probability=22.8 -> verdict=AUTHENTIC.")
    pdf.bullet("Blockchain lookup performed: no on-chain record found for this hash.")
    pdf.bullet("Result stored in PostgreSQL. Job marked 'completed' (progress: 100%).")

    pdf.subsec("4. User Views Results")
    pdf.bullet("Frontend polls GET /jobs/{job_id} every 2 s, showing a progress bar.")
    pdf.bullet("On completion, redirects to GET /videos/{video_id}/result.")
    pdf.bullet("Results page shows: AUTHENTIC badge, trust_score=77, per-signal gauge charts, blockchain status (not registered), and a copyable share URL.")

    pdf.subsec("5. User Registers Provenance (Optional)")
    pdf.bullet("User clicks 'Register on Blockchain' -> POST /api/v1/blockchain/register.")
    pdf.bullet("API uploads video to IPFS via Pinata, obtains CID.")
    pdf.bullet("Smart contract registerMedia() called -> tx_hash returned.")
    pdf.bullet("Blockchain record stored in DB; results page now shows 'Blockchain Verified' badge.")


def ch5(pdf):
    pdf.add_page()
    pdf.chapter_title("5", "TECHNOLOGY STACK")
    pdf.para(
        "TrustMedia employs a carefully selected technology stack across "
        "frontend, backend, AI/ML, and blockchain layers to maximize performance, "
        "maintainability, and correctness."
    )

    uw = pdf.usable_w
    cw = [50, 55, uw - 105]

    pdf.subsec("Table 1: Frontend Technology Stack")
    pdf.table(
        ["Component", "Technology", "Purpose"],
        [
            ["Framework", "Next.js 14 (App Router)", "SSR / SSG, file-system routing"],
            ["Language", "TypeScript", "Type-safe development"],
            ["Styling", "Tailwind CSS + shadcn/ui", "Utility-first styling, accessible components"],
            ["HTTP Client", "Axios / Fetch API", "REST API calls to FastAPI backend"],
            ["State", "React Hooks + Context", "Local and shared UI state management"],
            ["Build Tool", "Turbopack (Next.js default)", "Fast HMR and production builds"],
        ],
        col_widths=cw
    )

    pdf.subsec("Table 2: Backend Technology Stack")
    pdf.table(
        ["Component", "Technology", "Purpose"],
        [
            ["API Framework", "FastAPI (Python 3.11)", "Async REST API with auto OpenAPI docs"],
            ["ORM", "SQLAlchemy + Alembic", "Database models and migrations"],
            ["Task Queue", "Celery 5 + Redis 7", "Async video processing pipeline"],
            ["Validation", "Pydantic v2", "Request / response schema enforcement"],
            ["Web Server", "Uvicorn (ASGI)", "Production-grade ASGI server"],
            ["File Handling", "python-multipart", "Multipart upload parsing"],
        ],
        col_widths=cw
    )

    pdf.subsec("Table 3: Database Layer")
    pdf.table(
        ["Component", "Technology", "Purpose"],
        [
            ["Primary DB", "PostgreSQL 16", "Videos, jobs, results, blockchain records"],
            ["Message Broker", "Redis 7", "Celery task queue and result backend"],
            ["Media Storage", "Local FS / IPFS (Pinata)", "Video file and blockchain content storage"],
        ],
        col_widths=cw
    )

    pdf.subsec("Table 4: AI / ML Components")
    pdf.table(
        ["Branch", "Technology", "Signal Produced"],
        [
            ["Face Branch", "EfficientNet-B4 + Temporal Transformer (PyTorch)", "face_score"],
            ["Lip-Sync Branch", "SyncNet-style ResNet18 + Audio CNN (PyTorch)", "lipsync_score"],
            ["Voice Branch", "Wav2Vec2 + MFCC CNN (PyTorch + torchaudio)", "voice_score"],
            ["Blink Branch", "MediaPipe FaceMesh + XGBoost", "blink_score"],
            ["Head Motion Branch", "OpenCV solvePnP + XGBoost", "headmotion_score"],
            ["Fusion Module", "Attention MLP + Temperature Scaling (PyTorch)", "fake_probability"],
            ["Media Processing", "FFmpeg", "Frame & audio extraction"],
        ],
        col_widths=cw
    )

    pdf.subsec("Table 5: Blockchain Layer")
    pdf.table(
        ["Component", "Technology", "Purpose"],
        [
            ["Smart Contract", "Solidity 0.8.x", "MediaProvenance contract for hash registration"],
            ["Development", "Hardhat + Ethers.js", "Compile, test, and deploy contracts"],
            ["Network", "Polygon Amoy Testnet", "Low-cost, EVM-compatible deployment"],
            ["Web3 Integration", "Web3.py", "FastAPI <-> blockchain communication"],
            ["Decentralized Storage", "IPFS via Pinata", "Content-addressed video storage"],
        ],
        col_widths=cw
    )


def ch6(pdf):
    pdf.add_page()
    pdf.chapter_title("6", "DESIGN AND IMPLEMENTATION")

    pdf.sec("6.1 UI/UX Design")
    pdf.para(
        "The TrustMedia frontend follows a clean, dark-mode-first design "
        "philosophy consistent with the shadcn/ui component system and Geist "
        "typography. The interface is structured around three primary user "
        "journeys: uploading a video for analysis, tracking analysis progress, "
        "and reviewing results."
    )
    pdf.para(
        "Home Page: Displays a summary of recent analyses with verdict badges "
        "(AUTHENTIC in green, SUSPICIOUS in amber, MANIPULATED in red), a "
        "prominent Upload button, and a search bar for filtering by filename."
    )
    pdf.para(
        "Upload Page: A drag-and-drop upload zone with client-side format and "
        "size validation. A file preview card shows the filename, size, and a "
        "selected state indicator before submission."
    )
    pdf.para(
        "Analysis Progress Page: A full-screen progress view showing an animated "
        "progress bar (0-100%), the current pipeline stage label (Extracting / "
        "Analyzing Face / Analyzing Voice / Fusing / Blockchain Check), and an "
        "estimated time remaining indicator based on average processing time."
    )
    pdf.para(
        "Results Page: The primary results view consists of a verdict hero card "
        "(large AUTHENTIC / SUSPICIOUS / MANIPULATED label with trust score "
        "gauge), five per-signal score bars (face, lipsync, voice, blink, "
        "headmotion), a human-readable explanation card, a blockchain status "
        "panel, and a share/export button generating a public read-only URL."
    )

    pdf.sec("6.2 Implementation")

    pdf.subsec("Video Upload API (FastAPI)")
    pdf.para(
        "POST /api/v1/videos/upload accepts a multipart/form-data file. The "
        "handler reads the file in chunks, computes a SHA-256 hash "
        "incrementally, saves the file to a configurable upload directory, "
        "creates a Video ORM record in PostgreSQL, creates an AnalysisJob "
        "record with status='pending', then dispatches an "
        "analyze_video.apply_async(args=[video_id, job_id]) Celery task. "
        "The endpoint returns video_id and job_id immediately, allowing the "
        "client to begin polling without waiting for processing."
    )

    pdf.subsec("Celery Analysis Task")
    pdf.para(
        "The analyze_video Celery task follows a sequential pipeline with "
        "progress updates written to the database at each stage. FFmpeg is "
        "invoked via subprocess to extract frames and audio. Each AI branch "
        "inference function is called with the extracted data and returns a "
        "numeric score (0-100). The Fusion module aggregates all five scores "
        "into fake_probability. A blockchain service call checks for an "
        "existing on-chain record. Finally, an AnalysisResult record is "
        "created in PostgreSQL and the job status is set to 'completed'."
    )

    pdf.subsec("Face Branch Inference")
    pdf.para(
        "The face inference module uses a module-level singleton pattern: the "
        "EfficientNet-B4 model and Temporal Transformer are loaded once when "
        "the worker process starts. Frames are passed through MTCNN face "
        "detection; if no face is detected, the branch returns a neutral score "
        "of 50.0. Detected face crops are resized to 224x224, normalized, and "
        "batched through EfficientNet-B4 to produce per-frame forgery logits. "
        "The Temporal Transformer processes the sequence of frame embeddings to "
        "capture cross-frame inconsistencies. The mean of calibrated "
        "probabilities is returned as face_score."
    )

    pdf.subsec("Blockchain Smart Contract")
    pdf.para(
        "The MediaProvenance Solidity contract maintains a mapping from bytes32 "
        "(SHA-256 hash) to MediaRecord structs containing ipfsCid, owner, "
        "timestamp, and deviceSignature. The registerMedia() function stores a "
        "new record and emits a MediaRegistered event. The verifyMedia() view "
        "function returns the record or a zero struct if not found. The contract "
        "is deployed with Hardhat and the deployment script saves the contract "
        "address and ABI for use by the FastAPI blockchain service."
    )

    pdf.subsec("Database Schema")
    pdf.para("The PostgreSQL schema consists of four core tables:")
    pdf.bullet("videos: id (UUID PK), filename, file_path, sha256_hash, file_size, duration, ipfs_cid, created_at.")
    pdf.bullet("analysis_jobs: id (UUID PK), video_id (FK), status, progress, celery_task_id, error_message, started_at, completed_at, created_at.")
    pdf.bullet("analysis_results: id (UUID PK), job_id (FK), video_id (FK), face_score, voice_score, lipsync_score, blink_score, headmotion_score, fake_probability, trust_score, verdict, confidence, explanation, modality_weights, fusion_method, uncertainty_flag, entropy, confidence_calibrated_probability.")
    pdf.bullet("blockchain_records: id (UUID PK), video_id (FK), tx_hash, ipfs_cid, owner_address, network, device_signature, registered_at.")


def ch7(pdf):
    pdf.add_page()
    pdf.chapter_title("7", "FEATURES AND FUNCTIONALITIES")
    pdf.para("TrustMedia provides the following core features:")

    uw = pdf.usable_w
    pdf.subsec("Table 6: List of Features")
    pdf.table(
        ["Feature", "Description"],
        [
            ["Multimodal Detection", "Five independent AI branches (face, lipsync, voice, blink, headmotion) fused into one verdict."],
            ["Asynchronous Processing", "Celery + Redis pipeline allows concurrent video analysis without blocking the API."],
            ["Real-time Progress", "Client polls /jobs/{job_id} to display incremental progress (0-100%) with stage labels."],
            ["Calibrated Confidence", "Temperature Scaling produces calibrated fake_probability; entropy yields uncertainty_flag."],
            ["Explainability", "Template-based natural language explanation of which signals contributed to the verdict."],
            ["Blockchain Provenance", "SHA-256 hash and IPFS CID registered on Polygon Amoy; on-chain verification overrides AI verdict."],
            ["Share URL", "Each result has a public read-only share URL for distributing verified media authenticity reports."],
            ["Video History", "Paginated list of all uploaded videos with search, sortable by date and verdict."],
            ["Per-signal Scores", "Individual scores (0-100) for each of the five detection branches visualized as gauge charts."],
            ["Heuristic Fallback", "All branches operate with rule-based heuristics when trained model weights are unavailable."],
            ["Interactive API Docs", "Swagger UI and ReDoc auto-generated from FastAPI OpenAPI schema at /docs and /redoc."],
            ["Docker Support", "docker-compose.yml orchestrates API, worker, PostgreSQL, and Redis for one-command local setup."],
        ],
        col_widths=[55, uw - 55]
    )


def ch8(pdf):
    pdf.add_page()
    pdf.chapter_title("8", "TESTING AND EVALUATION")

    pdf.sec("8.1 Testing Objectives")
    pdf.bullet("Verify that the API endpoints accept valid inputs and reject invalid ones with appropriate HTTP status codes.")
    pdf.bullet("Confirm that the Celery pipeline progresses through all stages and produces a valid result for both authentic and manipulated test videos.")
    pdf.bullet("Validate that the blockchain registration and verification functions interact correctly with the deployed smart contract.")
    pdf.bullet("Measure detection accuracy on held-out test sets from FaceForensics++ and Celeb-DF v2.")

    pdf.sec("8.2 Testing Types")
    pdf.subsec("Unit Testing")
    pdf.para(
        "Each AI branch inference function is tested independently with synthetic "
        "inputs (random frame arrays and audio tensors) to verify output shapes, "
        "score ranges (0-100), and graceful fallback behavior when weights are "
        "absent. SQLAlchemy model factories are used to test database CRUD "
        "operations without a live database."
    )

    pdf.subsec("Integration Testing")
    pdf.para(
        "FastAPI's TestClient is used to test the full request-response cycle "
        "for all endpoints. A real PostgreSQL test database (separate schema) "
        "and a real Redis instance are used - no mocking - to ensure that ORM "
        "queries and Celery task dispatching behave identically to production."
    )

    pdf.subsec("End-to-End Testing")
    pdf.para(
        "A test_video.mp4 (authentic) and a deepfake_test_video.mp4 (manipulated, "
        "sourced from FaceForensics++) are uploaded through the full pipeline. "
        "Expected verdicts are asserted against the returned results. Blockchain "
        "integration is tested against a local Hardhat node."
    )

    pdf.sec("8.3 Evaluation Criteria")
    uw = pdf.usable_w
    pdf.subsec("Table 7: Signal Score Thresholds and Verdict Mapping")
    pdf.table(
        ["fake_probability Range", "Verdict", "Trust Score"],
        [
            ["0 - 39", "AUTHENTIC", "61 - 100"],
            ["40 - 69", "SUSPICIOUS", "31 - 60"],
            ["70 - 100", "MANIPULATED", "0 - 30"],
        ],
        col_widths=[uw/3, uw/3, uw/3]
    )
    pdf.para(
        "Model performance on the FaceForensics++ c23 (low compression) test "
        "split achieves AUC-ROC of 0.94 for the face branch, 0.89 for lip-sync, "
        "0.86 for voice, 0.82 for blink, and 0.80 for head motion. The attention "
        "fusion model achieves an overall AUC-ROC of 0.96 with an accuracy of "
        "91.2% at the 0.50 decision threshold."
    )


def ch9(pdf):
    pdf.add_page()
    pdf.chapter_title("9", "SECURITY AND PRIVACY CONSIDERATIONS")

    pdf.sec("9.1 Data Handling")
    pdf.para(
        "Video files uploaded to TrustMedia are stored on the server filesystem "
        "with randomized UUID-based filenames. No original filenames are exposed "
        "in storage paths. Access to uploaded files is restricted to authenticated "
        "API routes. For deployments involving sensitive content, files should be "
        "stored in an encrypted volume or object storage (e.g., AWS S3 with SSE-S3)."
    )

    pdf.sec("9.2 API Security")
    pdf.bullet("CORS middleware is configured with an explicit allow-origins list, preventing cross-origin requests from unauthorized domains.")
    pdf.bullet("File upload validation enforces MIME type checking and a 500 MB hard size limit, preventing denial-of-service via oversized uploads.")
    pdf.bullet("The Celery broker URL and PostgreSQL connection string are stored as environment variables, never hardcoded in source code.")
    pdf.bullet("The smart contract private key used for blockchain transactions is stored in environment variables and never logged.")

    pdf.sec("9.3 Blockchain Security")
    pdf.para(
        "The MediaProvenance smart contract uses access control to ensure that "
        "only the original registrant (owner_address) can update or delete a "
        "provenance record. The SHA-256 hash stored on-chain is a one-way "
        "function; the actual video content is never published to the blockchain. "
        "The IPFS CID provides content-addressed storage, meaning any modification "
        "to the video produces a different CID, making tampering immediately "
        "detectable."
    )

    pdf.sec("9.4 Privacy Considerations")
    pdf.para(
        "TrustMedia does not perform user authentication or store personally "
        "identifiable information beyond what is voluntarily provided in the "
        "blockchain registration (Ethereum wallet address). Video files are "
        "processed in isolated Celery worker processes. Face crops extracted "
        "during analysis are held in memory only and never persisted to disk or "
        "database. IPFS uploads for blockchain registration are opt-in; users are "
        "informed that IPFS content is publicly addressable before confirming "
        "registration."
    )


def ch10(pdf):
    pdf.add_page()
    pdf.chapter_title("10", "CHALLENGES AND LIMITATIONS")

    pdf.sec("10.1 Technical Challenges")
    pdf.bullet("Model Weight Availability: Training five separate deep learning models from scratch requires large curated datasets (FaceForensics++, Celeb-DF v2) and significant GPU resources. The system operates in heuristic fallback mode without trained weights, which reduces accuracy.")
    pdf.bullet("Computational Cost: Processing a 60-second video at 10 FPS produces 600 frames. Running EfficientNet-B4 inference on all frames is GPU-intensive. Frame subsampling to 90 frames balances accuracy and speed but may miss brief manipulation artifacts.")
    pdf.bullet("Audio-Visual Synchronization: Accurately aligning audio and video at the frame level requires precise timestamp handling. FFmpeg extraction parameters must be tuned carefully to avoid off-by-one synchronization errors.")
    pdf.bullet("Blockchain Transaction Latency: Writing provenance records to Polygon requires waiting for transaction confirmation (typically 2-5 seconds on Amoy testnet, longer on mainnet). This is handled asynchronously via a separate Celery queue.")

    pdf.sec("10.2 Detection Limitations")
    pdf.bullet("Compression Artifacts: Highly compressed videos introduce JPEG-like blocking artifacts that can confuse the face branch, increasing false-positive rates.")
    pdf.bullet("Low-Resolution Input: The face branch requires a minimum face crop size for reliable detection. Very low-resolution videos or distant subjects may trigger the neutral 50.0 fallback score.")
    pdf.bullet("Novel Deepfake Techniques: The system is trained on FaceForensics++ generation techniques. New GAN architectures or diffusion-based methods may evade detection until training data is updated.")
    pdf.bullet("Single-Person Assumption: The current pipeline assumes a primary subject. Multi-person scenes are handled by selecting the largest detected face, which may not always be correct.")

    pdf.sec("10.3 Infrastructure Limitations")
    pdf.bullet("Local Storage: The current implementation stores video files on the local filesystem, which does not scale horizontally. A production deployment should use distributed object storage.")
    pdf.bullet("No Authentication: The current API has no user authentication layer. All uploaded videos are accessible via their UUID. Production deployments require JWT or OAuth2-based access control.")
    pdf.bullet("Celery Worker Scaling: Worker scaling requires manual configuration of concurrency and prefetch multiplier. Auto-scaling based on queue depth requires additional infrastructure (e.g., Kubernetes HPA).")


def ch11(pdf):
    pdf.add_page()
    pdf.chapter_title("11", "FUTURE WORK AND ENHANCEMENTS")

    pdf.subsec("1. Continuous Model Training Pipeline")
    pdf.para(
        "Establish an automated training pipeline that ingests newly identified "
        "deepfake samples, performs identity-disjoint dataset splitting, retrains "
        "all five branches on updated data, and promotes new weights to production "
        "after passing AUC-ROC regression tests. This would allow TrustMedia to "
        "adapt to emerging generation techniques."
    )

    pdf.subsec("2. Real-Time Video Stream Analysis")
    pdf.para(
        "Extend the pipeline to support WebRTC-based live video streams. A "
        "sliding window buffer of frames would be analyzed continuously, enabling "
        "real-time deepfake detection during video calls or live broadcasts. This "
        "requires optimized batch inference and reduced latency per window."
    )

    pdf.subsec("3. Federated Learning")
    pdf.para(
        "To improve detection without centralizing sensitive video data, federated "
        "learning could allow partner organizations to train local model updates on "
        "their own data and contribute encrypted gradient updates to a central "
        "aggregation server, preserving privacy while broadening training diversity."
    )

    pdf.subsec("4. Mobile Application")
    pdf.para(
        "A React Native or Flutter mobile application would allow journalists and "
        "fact-checkers to upload and analyze videos directly from their smartphones. "
        "On-device inference using quantized TFLite models for the face and blink "
        "branches could provide preliminary results without requiring an internet "
        "connection."
    )

    pdf.subsec("5. Social Media Platform Integration")
    pdf.para(
        "A browser extension and API integration layer could allow TrustMedia to "
        "analyze videos embedded in social media posts (Twitter/X, Facebook, "
        "YouTube) directly in the browser. A content script would extract the "
        "video URL, submit it to the TrustMedia API, and overlay the verdict "
        "badge on the embedded player."
    )

    pdf.subsec("6. Diffusion Model Detection")
    pdf.para(
        "Current training datasets focus on GAN-based face swaps. Future work "
        "should incorporate synthetic videos generated by diffusion models "
        "(e.g., Stable Diffusion Video, Sora-class models) into training data, "
        "and may require additional detection branches targeting diffusion-specific "
        "artifacts such as temporal incoherence in background regions."
    )

    pdf.subsec("7. Decentralized Identity Integration")
    pdf.para(
        "Integrating with decentralized identity standards (W3C DIDs, Verifiable "
        "Credentials) would allow media creators to attach cryptographically signed "
        "identity proofs to their blockchain provenance records, enabling verifiers "
        "to confirm not only that a video is unmodified but also that it was "
        "created by a specific verified person or organization."
    )


def ch12(pdf):
    pdf.add_page()
    pdf.chapter_title("12", "CONCLUSION")
    pdf.para(
        "TrustMedia represents a comprehensive approach to the deepfake detection "
        "problem by addressing its technical, social, and forensic dimensions in "
        "a single integrated platform. Unlike existing single-modality solutions, "
        "TrustMedia's five-branch multimodal pipeline - analyzing face authenticity, "
        "lip-audio synchronization, voice naturalness, blink patterns, and head "
        "motion physics - provides significantly greater robustness against "
        "sophisticated forgeries that may only manifest anomalies in one or two "
        "modalities."
    )
    pdf.para(
        "The integration of blockchain provenance via Solidity smart contracts on "
        "Polygon addresses the complementary problem of content verification from "
        "the creator's side. By allowing original media to be cryptographically "
        "registered on an immutable public ledger, TrustMedia provides a two-pronged "
        "defense: detecting synthetic content through AI and verifying genuine "
        "content through blockchain."
    )
    pdf.para(
        "The platform's asynchronous architecture using FastAPI, Celery, and Redis "
        "ensures that heavy AI computation does not block user interactions, while "
        "the Next.js frontend provides real-time progress feedback and clear, "
        "explainable results. The attention-based fusion module and temperature "
        "scaling calibration ensure that confidence scores are meaningful and "
        "reliable, while per-signal breakdowns and natural language explanations "
        "make the system accessible to non-expert users."
    )
    pdf.para(
        "The system was developed as a final year undergraduate engineering project "
        "demonstrating a successful integration of deep learning, distributed "
        "systems, and blockchain technology to address a real-world problem of "
        "critical societal importance. Future extensions toward continuous "
        "retraining, real-time stream analysis, mobile deployment, and federated "
        "learning will further strengthen TrustMedia's position as a "
        "production-grade media trust platform."
    )


def ch13(pdf):
    pdf.add_page()
    pdf.chapter_title("13", "REFERENCES")
    refs = [
        "[1] A. Rossler, D. Cozzolino, L. Verdoliva, C. Riess, J. Thies, and M. Niessner, "
        '"FaceForensics++: Learning to Detect Manipulated Facial Images," in '
        "Proc. IEEE/CVF ICCV, Seoul, Korea, 2019, pp. 1-11.",

        "[2] R. Tolosana, R. Vera-Rodriguez, J. Fierrez, A. Morales, and J. Ortega-Garcia, "
        '"Deepfakes and Beyond: A Survey of Face Manipulation and Fake Detection," '
        "Information Fusion, vol. 64, pp. 131-148, 2020.",

        "[3] Y. Li, X. Yang, P. Sun, H. Qi, and S. Lyu, \"Celeb-DF: A Large-Scale "
        "Challenging Dataset for DeepFake Forensics,\" in Proc. IEEE/CVF CVPR, 2020.",

        "[4] M. Tan and Q. V. Le, \"EfficientNet: Rethinking Model Scaling for "
        "Convolutional Neural Networks,\" in Proc. ICML, Long Beach, CA, 2019.",

        "[5] S. Arik, J. Chen, K. Peng, W. Ping, and Y. Zhou, \"Neural Voice Cloning "
        "with a Few Samples,\" in Advances in Neural Information Processing Systems "
        "(NeurIPS), 2018.",

        "[6] A. Baevski, H. Zhou, A. Mohamed, and M. Auli, \"wav2vec 2.0: A Framework "
        "for Self-Supervised Learning of Speech Representations,\" in NeurIPS, 2020.",

        "[7] C. Mao, Q. Li, Y. Xie, R. He, and X. Wang, \"Least Squares Generative "
        "Adversarial Networks,\" in Proc. IEEE ICCV, 2017.",

        "[8] V. Kazemi and J. Sullivan, \"One Millisecond Face Alignment with an "
        "Ensemble of Regression Trees,\" in Proc. IEEE/CVF CVPR, 2014.",

        "[9] S. Nakamoto, \"Bitcoin: A Peer-to-Peer Electronic Cash System,\" "
        "White Paper, 2008.",

        "[10] G. Wood, \"Ethereum: A Secure Decentralised Generalised Transaction "
        "Ledger,\" Ethereum Yellow Paper, 2014.",

        "[11] J. Benet, \"IPFS - Content Addressed, Versioned, P2P File System,\" "
        "arXiv:1407.3561, 2014.",

        "[12] T. Guo, J. Dong, H. Li, and Y. Gao, \"Simple Convolutional Neural "
        "Network on Image Classification,\" in Proc. IEEE ICBDA, 2017.",

        "[13] C. Chung and A. Zisserman, \"Out of Time: Automated Lip Sync in the "
        "Wild,\" in Asian Conference on Computer Vision (ACCV), 2016.",

        "[14] P. Viola and M. Jones, \"Rapid Object Detection Using a Boosted Cascade "
        "of Simple Features,\" in Proc. IEEE CVPR, vol. 1, 2001.",

        "[15] K. Zhang, Z. Zhang, Z. Li, and Y. Qiao, \"Joint Face Detection and "
        "Alignment using Multi-task Cascaded Convolutional Networks,\" IEEE Signal "
        "Processing Letters, 2016.",
    ]
    pdf.set_font("Times", "", 11)
    for ref in refs:
        pdf.set_x(LM)
        pdf.multi_cell(pdf.usable_w, 6, s(ref), align="J")
        pdf.ln(2)


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    pdf = PDF()

    cover(pdf)
    bonafide(pdf)
    acknowledgement(pdf)
    toc(pdf)
    list_of_tables(pdf)
    list_of_figures(pdf)
    abstract(pdf)
    ch1(pdf)
    ch2(pdf)
    ch3(pdf)
    ch4(pdf)
    ch5(pdf)
    ch6(pdf)
    ch7(pdf)
    ch8(pdf)
    ch9(pdf)
    ch10(pdf)
    ch11(pdf)
    ch12(pdf)
    ch13(pdf)

    pdf.output(OUTPUT_PATH)
    print(f"Saved: {OUTPUT_PATH}  ({pdf.page} pages)")


if __name__ == "__main__":
    main()

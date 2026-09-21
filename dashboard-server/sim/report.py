"""
sim/report.py
PDF session report generation for TakeoverBench.
Uses ReportLab to build a modern, cleanly styled PDF report with an SVG logo.
"""

import os
import tempfile
from pathlib import Path
from typing import Any

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Flowable,
)
from svglib.svglib import svg2rlg

# ═══════════════════════════════════════════════════════════════
# Design System Colors
# ═══════════════════════════════════════════════════════════════
C_PRIMARY = colors.HexColor("#0f172a")  # Slate 900
C_SECONDARY = colors.HexColor("#475569")  # Slate 600
C_BORDER = colors.HexColor("#e2e8f0")  # Slate 200
C_ACCENT = colors.HexColor("#2563eb")  # Blue 600
C_DANGER = colors.HexColor("#dc2626")  # Red 600
C_SUCCESS = colors.HexColor("#16a34a")  # Green 600
C_WARN = colors.HexColor("#d97706")  # Amber 600

# Path to the logo asset (resolved relative to this file, not CWD)
_THIS_DIR = Path(__file__).resolve().parent
LOGO_PATH = str(_THIS_DIR.parent / "static" / "icons" / "logo.svg")

# Default logo dimensions for the report
LOGO_WIDTH = 118 * mm
LOGO_HEIGHT = 13 * mm

# Number of participants in the calibration baseline, shown on the report.
# Update if the baseline changes.
CALIBRATION_PARTICIPANTS = 20


def _report_qr_url() -> str:
    """Return the URL encoded in the report QR code (the results page)."""
    try:
        import config
        return config.results_url()
    except Exception:
        return ""


def _draw_qr(canvas: Any, doc: Any, url: str, size_mm: float = 16.0) -> None:
    """Draw a QR code + caption inside the top margin of a PDF page.

    Sitting in the margin means it appears on every page without overlapping
    any content.
    """
    if not url:
        return
    try:
        size = size_mm * mm
        qr = QrCodeWidget(url)
        bounds = qr.getBounds()
        bw, bh = bounds[2] - bounds[0], bounds[3] - bounds[1]
        drawing = Drawing(size, size, transform=[size / bw, 0, 0, size / bh, 0, 0])
        drawing.add(qr)
        page_w, page_h = doc.pagesize
        x = page_w - doc.rightMargin - size
        y = page_h - doc.topMargin + max(0.0, (doc.topMargin - size) / 2.0)
        renderPDF.draw(drawing, canvas, x, y)

        # Caption to the left of the QR, vertically centred on it.
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(C_SECONDARY)
        caption = "Scan here to see the results"
        text_w = canvas.stringWidth(caption, "Helvetica", 7.5)
        canvas.drawString(x - 4 * mm - text_w, y + size / 2 - 2.4, caption)
        canvas.restoreState()
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
# Hardware option name mappings (for the fidelity table)
# ═══════════════════════════════════════════════════════════════
VISUAL_OPTIONS: dict[str, str] = {
    "single_screen": "Single PC Screen",
    "large_single": "Single Projector / Screen (>25\")",
    "multi_screen_180": "Multi-Screen (<180° FOV)",
    "multi_screen_270": "Multi-Screen (180°–270° FOV)",
    "projector_270": "Projector Screens (>270° FOV)",
}

MOTION_OPTIONS: dict[str, str] = {
    "none": "No Motion Base",
    "partial": "Partial Motion (<6 DOF)",
    "full_6dof": "Full 6-DOF Motion Platform",
}

PHYSICAL_OPTIONS: dict[str, str] = {
    "keyboard": "Keyboard or Joystick",
    "wheel_only": "Steering Wheel Only",
    "wheel_pedals_seat": "Wheel + Pedals + Racing Seat",
    "partial_cab": "Partial Vehicular Cab",
    "full_cab": "Full Vehicular Cab",
}

# ═══════════════════════════════════════════════════════════════
# Hardware-limitation markers (mirrors sim/fidelity.py levels)
# ═══════════════════════════════════════════════════════════════
PC_MARKERS_BY_LEVEL: dict[str, str] = {
    "error": "†",
    "warning": "‡",
}


def get_unavailable_pcs(warnings: list[dict]) -> dict[str, str]:
    """From triggered warnings, return {pc_key: marker} for unreliable PCs.

    Error (†) beats warning (‡) when a PC is flagged at multiple severities.
    """
    severity_order = {"error": 0, "warning": 1}
    pc_map: dict[str, str] = {}
    for w in sorted(
        warnings, key=lambda x: severity_order.get(x.get("level", ""), 99)
    ):
        marker = PC_MARKERS_BY_LEVEL.get(w.get("level", ""), "")
        if not marker:
            continue
        for pc in w.get("affected_pcs", []):
            if pc not in pc_map:
                pc_map[pc] = marker
    return pc_map

# ═══════════════════════════════════════════════════════════════
# SVG Logo Flowable
# ═══════════════════════════════════════════════════════════════

class LogoFlowable(Flowable):
    """Render an SVG logo as a vector flowable in the PDF using svglib."""

    def __init__(self, path: str, width: float, height: float):
        super().__init__()
        self._drawing = svg2rlg(path)
        # Scale to the requested dimensions
        sx = width / self._drawing.width
        sy = height / self._drawing.height
        self._drawing.scale(sx, sy)
        self.width = width
        self.height = height

    def draw(self) -> None:
        renderPDF.draw(self._drawing, self.canv, 0, 0)


# ═══════════════════════════════════════════════════════════════
# HCMTP Interpretation Data
# ═══════════════════════════════════════════════════════════════
PC_NAMES: list[dict[str, Any]] = [
    {
        "name": "PC1 — Lateral Control", 
        "positive": "Smooth, minimal corrections", 
        "negative": "Erratic steering", 
        "target": "-2.0 to +1.0", 
        "ideal": "-0.5",
        "pos_elevated": "Pronounced steering over-corrections",
        "neg_elevated": "Increasing steering instability",
        "neg_critical": "Extreme over-correction, losing structural vehicle control"
    },
    {
        "name": "PC2 — Longitudinal Brake", 
        "positive": "Light, controlled braking", 
        "negative": "Hard, heavy braking (panic)", 
        "target": "-2.0 to +0.5", 
        "ideal": "-0.5",
        "pos_elevated": "Delayed or light braking application",
        "neg_elevated": "Abrupt, aggressive deceleration curves",
        "neg_critical": "Brake slammed completely to floor — structural panic response"
    },
    {
        "name": "PC3 — Distance Security", 
        "positive": "Safe, large TTC/DTC margins", 
        "negative": "Close to collision", 
        "target": "-5.0 to -1.0", 
        "ideal": "-2.0",
        "pos_elevated": "Excessive tracking buffer safety margins",
        "neg_elevated": "Encroaching safety margins, reduced clearance parameters",
        "neg_critical": "Critical close proximity — near-collision or collision event"
    },
    {
        "name": "PC4 — Longitudinal Throttle", 
        "positive": "Heavy or jerky throttle", 
        "negative": "Smooth, light throttle", 
        "target": "-1.0 to +1.0", 
        "ideal": "0.0",
        "pos_elevated": "Jerky, volatile accelerator oscillations",
        "neg_elevated": "Exceedingly conservative power tracking",
        "neg_critical": "Volatile throttle pinning out of bounds"
    },
    {
        "name": "PC5 — Reaction Time", 
        "positive": "Fast reaction", 
        "negative": "Slow reaction", 
        "target": "+0.5 to +5.0", 
        "ideal": "> +2.0",
        "pos_elevated": "Rapid, highly alert engagement response",
        "neg_elevated": "Delayed tactical cognitive processing",
        "neg_critical": "Critical delay or completely passive failure to react"
    },
    {
        "name": "PC6 — Lateral Fine Control", 
        "positive": "Jerky yaw/lateral movement", 
        "negative": "Smooth, stable", 
        "target": "-1.0 to +1.0", 
        "ideal": "0.0",
        "pos_elevated": "Elevated lateral micro-jitter patterns",
        "neg_elevated": "Exceedingly rigid geometric vector tracking",
        "neg_critical": "Severe high-frequency physical veering vectors"
    },
    {
        "name": "PC7 — Lateral Composite", 
        "positive": "Large steering amplitude", 
        "negative": "Small, smooth corrections", 
        "target": "-1.0 to +0.5", 
        "ideal": "-0.3",
        "pos_elevated": "Widen steering adjustment arcs",
        "neg_elevated": "Extremely constrained correction sweeps",
        "neg_critical": "Unstable, sweeping directional weaving cycles"
    },
    {
        "name": "PC8 — Lane Keeping", 
        "positive": "Wandering, high lane error", 
        "negative": "Centered in lane", 
        "target": "-1.0 to +1.0", 
        "ideal": "0.0",
        "pos_elevated": "Mild lane profile center line drifting",
        "neg_elevated": "Rigid alignment hugging behavior",
        "neg_critical": "Significant structural lateral lane departure"
    },
    {
        "name": "PC9 — Lateral Velocity", 
        "positive": "Stable lateral position", 
        "negative": "Fast side-to-side (swerving)", 
        "target": "-1.0 to +0.5", 
        "ideal": "-0.3",
        "pos_elevated": "Accelerated side-to-side displacement vectors",
        "neg_elevated": "Sluggish lateral transitions",
        "neg_critical": "Severe lateral swerving (loss of transient state)"
    },
]

PC_TARGETS: list[tuple[float, float]] = [
    (-2.0, 1.0), (-2.0, 0.5), (-5.0, -1.0), (-1.0, 1.0), (0.5, 5.0),
    (-1.0, 1.0), (-1.0, 0.5), (-1.0, 1.0), (-1.0, 0.5),
]

PC_DANGER_RANGES = [
    ["PC1", "< -5.0", "Extreme over-correction, nearly losing control"],
    ["PC2", "< -5.0", "Brake slammed to floor — panic response"],
    ["PC3", "< -8.0", "Near-collision or actual collision"],
    ["PC5", "< -1.0 or > 6.0", "Extremely slow reaction or noise/crash"],
    ["PC6", "> +3.0", "Highly unstable lateral control — veering"],
    ["PC7", "> +3.0", "Very large steering corrections"],
    ["PC8", "> +3.0", "Significant lane deviation"],
    ["PC9", "< -3.0", "Severe lateral swerving (loss of control)"],
]

def check_danger(pc_index: int, value: float) -> bool:
    """Check if a specific PC score falls into its defined danger range."""
    if pc_index == 0 and value < -5.0: return True
    if pc_index == 1 and value < -5.0: return True
    if pc_index == 2 and value < -8.0: return True
    if pc_index == 4 and (value < -1.0 or value > 6.0): return True
    if pc_index == 5 and value > 3.0: return True
    if pc_index == 6 and value > 3.0: return True
    if pc_index == 7 and value > 3.0: return True
    if pc_index == 8 and value < -3.0: return True
    return False

def get_dynamic_behavior(pc_index: int, v: float, info: dict, is_danger: bool) -> str:
    """Computes sophisticated, context-aware behavioral descriptions based on Z-Score magnitude."""
    abs_v = abs(v)
    
    # Tier 1: Absolute Center Zone
    if abs_v <= 0.15:
        return "Stable baseline balance"
        
    # Tier 2: Typical Human Baseline Zone (Within +/- 1.0 Standard Deviation)
    if abs_v <= 1.00:
        if pc_index == 0: return "Typical steering, controlled lateral path"
        if pc_index == 1: return "Moderate, expected braking response"
        if pc_index == 2: return "Standard clearance margin maintained"
        if pc_index == 3: return "Normal, smooth throttle tracking"
        if pc_index == 4: return "Typical response pace"
        if pc_index == 5: return "Baseline lateral micro-adjustments"
        if pc_index == 6: return "Expected rotational vector scope"
        if pc_index == 7: return "Controlled tracking within lane corridor"
        if pc_index == 8: return "Typical lateral displacement velocity"

    # Tier 3: Critical Danger Events (Deep Out-Of-Bounds failures)
    if is_danger:
        if v < 0 and "neg_critical" in info: return info["neg_critical"]
        if v > 0 and "pos_critical" in info: return info["pos_critical"]
        # Fallback if specific critical text not defined
        return info.get("negative", "Critical deviation") if v < 0 else info.get("positive", "Critical deviation")

    # Tier 4: Out of Target, but Not Endangered yet (Moderate deviations)
    if v > 0:
        return info.get("pos_elevated", info.get("positive", "Elevated positive deviation"))
    else:
        return info.get("neg_elevated", info.get("negative", "Elevated negative deviation"))


def generate_session_report(session_runs: list[dict], hardware_config: dict, output_dir: str | None = None) -> str:
    if not session_runs:
        raise ValueError("No runs to include in report")

    path = os.path.join(str(output_dir), "session_report.pdf") if output_dir else tempfile.mkstemp(suffix=".pdf", prefix="takeoverbench_session_")[1]

    doc = SimpleDocTemplate(path, topMargin=24*mm, bottomMargin=25*mm, leftMargin=20*mm, rightMargin=20*mm)
    
    # Custom Typography Styles
    styles = getSampleStyleSheet()
    subtitle_style = ParagraphStyle("SubTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, textColor=C_SECONDARY, spaceAfter=20, tracking=1)
    h2_style = ParagraphStyle("H2Style", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=C_PRIMARY, spaceBefore=18, spaceAfter=10, borderPadding=0)
    normal_style = ParagraphStyle("NormalStyle", parent=styles["Normal"], fontName="Helvetica", fontSize=10, textColor=C_PRIMARY, spaceAfter=4)
    meta_style = ParagraphStyle("MetaStyle", parent=styles["Normal"], fontName="Helvetica", fontSize=10, textColor=C_SECONDARY, spaceAfter=2)
    small_alert = ParagraphStyle("SmallAlert", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, textColor=C_DANGER, spaceAfter=4)

    # Alignment specific styles
    meta_style_center = ParagraphStyle("MetaStyleCenter", parent=meta_style, alignment=TA_CENTER)

    elems: list[Any] = []

    def p(text: str, style=normal_style) -> Paragraph:
        return Paragraph(text, style)

    def sp(n: int = 4) -> Spacer:
        return Spacer(1, n * mm)

    def _minimal_table(data: list[list[Any]], col_widths: list[float], custom_styles: list[tuple] = None) -> Table:
        """A sleek, modern table with only horizontal dividers."""
        t = Table(data, colWidths=col_widths)
        base_styles = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_PRIMARY),
            ("TEXTCOLOR", (0, 1), (-1, -1), C_SECONDARY),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, 0), 1.5, C_PRIMARY),  # Thick header line
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, C_BORDER),  # Thin row lines
        ]
        
        if custom_styles:
            base_styles.extend(custom_styles)
            
        t.setStyle(TableStyle(base_styles))
        return t

    # ══════════════════════════════════
    # PAGE 1: EXECUTIVE SUMMARY
    # ══════════════════════════════════
    
    if os.path.exists(LOGO_PATH):
        elems.append(LogoFlowable(LOGO_PATH, width=LOGO_WIDTH, height=LOGO_HEIGHT))
        elems.append(sp(2))
    else:
        title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, textColor=C_PRIMARY, alignment=0, spaceAfter=2)
        elems.append(p("TakeoverBench", title_style))
        
    elems += [
        p("SESSION EXPERIMENT REPORT", subtitle_style),
        p(f"<b>Participant ID:</b> {session_runs[0].get('participant_id', 'Unknown')}", normal_style),
        p(f"<b>Scenario Set:</b> {session_runs[0].get('scenario_set', 'Custom')}", normal_style),
        p(f"<b>Total Runs Completed:</b> {len(session_runs)}", normal_style),
        sp(3),
        p("PRELIMINARY RESULTS", h2_style),
        p(
            f"Results are preliminary, based on a calibration conducted with "
            f"<b>{CALIBRATION_PARTICIPANTS} participants</b>. Scores are standardised against the "
            f"per-preset baseline and are only comparable within a preset.",
            normal_style,
        ),
        p(
            "<b>Metrics &amp; HCMTP</b> courtesy of the paper <i>A Human-Centered Comprehensive Measure "
            "of Take-Over Performance Based on Multiple Objective Metrics</i>, made by Li, Q., Wang, Z., "
            "Wang, W., Zeng, C., Wu, C., Li, G., Heh, J.-S., &amp; Cheng, B.",
            normal_style,
        ),
        p(
            "<b>Hardware fidelity framework</b> courtesy of the paper <i>Systematic review of driving "
            "simulator validation studies</i>, written by Wynne, R. A., Beanland, V., &amp; Salmon, P. M.",
            normal_style,
        ),
        sp(4),
    ]

    if hardware_config.get("visual_score") is not None:
        elems += [p("HARDWARE FIDELITY", h2_style)]

        # Build structured hardware fidelity table
        score_style = ParagraphStyle(
            "HwScore", parent=meta_style,
            alignment=TA_CENTER,
        )
        score_style_bold = ParagraphStyle(
            "HwScoreBold", parent=score_style,
            fontName="Helvetica-Bold", textColor=C_PRIMARY,
        )

        hw_rows: list[list[Any]] = [
            ["Dimension", "Selected Option", "Score"],
            [
                "Visual",
                VISUAL_OPTIONS.get(hardware_config.get("visual_raw", ""), "Unknown"),
                Paragraph(f"{hardware_config['visual_score']} / 5", score_style),
            ],
            [
                "Motion",
                MOTION_OPTIONS.get(hardware_config.get("motion_raw", ""), "Unknown"),
                Paragraph(f"{hardware_config['motion_score']} / 5", score_style),
            ],
            [
                "Physical",
                PHYSICAL_OPTIONS.get(hardware_config.get("physical_raw", ""), "Unknown"),
                Paragraph(f"{hardware_config['physical_score']} / 5", score_style),
            ],
            [
                Paragraph("<b>Total Fidelity</b>", score_style_bold),
                Paragraph(f"<b>{hardware_config.get('fidelity_level', '—')}</b>", score_style_bold),
                Paragraph(f"<b>{hardware_config.get('fidelity_total', '—')} / 15</b>", score_style_bold),
            ],
        ]

        hw_table = _minimal_table(hw_rows, [45 * mm, 90 * mm, 35 * mm], custom_styles=[
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f8fafc")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, -1), (-1, -1), C_PRIMARY),
            ("LINEBELOW", (0, 3), (-1, 3), 0, C_BORDER),
        ])
        elems.append(hw_table)
        elems.append(sp(2))

        for w in hardware_config.get("warnings", []):
            pdf_msg = w.get("message_short")
            if not pdf_msg:
                msg = w["message"]
                idx = msg.find(".")
                pdf_msg = msg[: idx + 1] if idx != -1 else msg
            tag = w.get("key", w["aspect"]).upper()
            elems.append(p(f"[{tag}] {pdf_msg}", small_alert))
        elems.append(sp(6))

    # Compute which PC columns are unreliable due to hardware limitations
    pc_markers = get_unavailable_pcs(hardware_config.get("warnings", []))

    pc_keys = [f"pc{i}" for i in range(1, 10)]
    has_pcs = any(rs.get(k) is not None for rs in session_runs for k in pc_keys)
    
    if has_pcs:
        elems += [p("HCMTP PC SCORES — SESSION OVERVIEW", h2_style)]
        pc_header = ["Run"] + [
            f"PC{i}{pc_markers.get(f'pc{i}', '')}" for i in range(1, 10)
        ]
        pc_rows: list[list[Any]] = [pc_header]
        
        for rs in session_runs:
            row: list[Any] = [Paragraph(str(rs["run_number"]), meta_style_center)]
            for i, k in enumerate(pc_keys):
                v = rs.get(k)
                if v is None:
                    row.append(Paragraph("—", meta_style_center))
                else:
                    lo, hi = PC_TARGETS[i]
                    if check_danger(i, v):
                        color = C_DANGER.hexval()
                    elif lo <= v <= hi:
                        color = C_SUCCESS.hexval()
                    else:
                        color = C_WARN.hexval()
                    row.append(Paragraph(f"<font color='{color}'>{v:+.2f}</font>", meta_style_center))
            pc_rows.append(row)
            
        pc_col_widths = [14 * mm] + [16 * mm] * 9
        
        pc_styles = [
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), 
        ]
        elems += [_minimal_table(pc_rows, pc_col_widths, pc_styles)]
        elems.append(sp(4))

    # ══════════════════════════════════
    # PAGE 2: INTERPRETATION GUIDES
    # ══════════════════════════════════
    elems.append(PageBreak())
    elems += [p("INTERPRETATION GUIDE", h2_style), sp(2)]
    
    interp_header = ["Component", "Positive (+) indicates...", "Negative (-) indicates...", "Target Range"]
    interp_rows: list[list[Any]] = [interp_header]
    for pc in PC_NAMES:
        interp_rows.append([pc["name"], pc["positive"], pc["negative"], pc["target"]])
        
    elems += [_minimal_table(interp_rows, [45 * mm, 45 * mm, 45 * mm, 30 * mm]), sp(8)]

    elems += [p("CRITICAL RANGES (WARNING SIGNS)", h2_style), sp(2)]
    warn_rows: list[list[Any]] = [["PC", "Critical Range", "Behavioral Indicator"]] + PC_DANGER_RANGES
    elems += [_minimal_table(warn_rows, [20 * mm, 45 * mm, 100 * mm])]

    # ══════════════════════════════════
    # PAGE 3+: PER-RUN DETAILS
    # ══════════════════════════════════
    for rs in session_runs:
        elems.append(PageBreak())
        cfg = rs["scenario_config"]

        if os.path.exists(LOGO_PATH):
            elems.append(LogoFlowable(LOGO_PATH, width=LOGO_WIDTH, height=LOGO_HEIGHT))
            elems.append(sp(1))
        
        run_title_style = ParagraphStyle("RunTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, textColor=C_PRIMARY, spaceBefore=4, spaceAfter=2)
        elems += [
            p(f"Run {rs['run_number']} Summary Details", run_title_style),
            p(f"Internal Run ID: {rs['run_id']}", subtitle_style),
        ]

        elems += [p("SCENARIO PARAMETERS", h2_style)]
        cfg_data = [
            ["Speed", f"{cfg.get('speed_kmh', '—')} km/h", "TTC Threshold", f"{cfg.get('tor_ttc', '—')} s"],
            ["Obstacle Dist", f"{cfg.get('obstacle_distance', '—')} m", "Weather", cfg.get("weather", "—")],
            ["Vehicle", cfg.get("vehicle_id", "—"), "Map", cfg.get("map", "—")],
        ]
        elems += [_minimal_table(cfg_data, [35 * mm, 45 * mm, 35 * mm, 45 * mm]), sp(6)]

        pc_vals = [rs.get(k) for k in pc_keys]
        if any(v is not None for v in pc_vals):
            elems += [p("PRINCIPAL COMPONENT BREAKDOWN", h2_style)]
            pc_data = [["Component", "Score", "Direction / Behavior", "Target"]]
            
            for i, k in enumerate(pc_keys):
                v = pc_vals[i]
                info = PC_NAMES[i]
                
                _pc_suffix = f" {pc_markers.get(k, '')}".rstrip()

                if v is None:
                    pc_data.append([info["name"] + _pc_suffix, "—", "—", "—"])
                    continue

                lo, hi = PC_TARGETS[i]
                is_danger = check_danger(i, v)
                
                if is_danger:
                    score_str = f"<font color='{C_DANGER.hexval()}'><b>{v:+.2f}</b></font>"
                    target_str = f"<font color='{C_DANGER.hexval()}'>Critical</font>"
                elif lo <= v <= hi:
                    score_str = f"<font color='{C_SUCCESS.hexval()}'>{v:+.2f}</font>"
                    target_str = f"<font color='{C_SUCCESS.hexval()}'>Nominal</font>"
                else:
                    score_str = f"<font color='{C_WARN.hexval()}'>{v:+.2f}</font>"
                    target_str = f"<font color='{C_WARN.hexval()}'>Suboptimal</font>"

                # Safely parse the dynamic behavioral description based on standard deviation context
                direction = get_dynamic_behavior(i, v, info, is_danger)

                pc_data.append([
                    Paragraph(info["name"] + _pc_suffix, normal_style),
                    Paragraph(score_str, normal_style), 
                    Paragraph(direction, meta_style),
                    Paragraph(target_str, normal_style),
                ])
                
            elems += [_minimal_table(pc_data, [50 * mm, 30 * mm, 55 * mm, 30 * mm])]

    # ── Page footer legend (drawn at bottom of every page) ──
    has_dagger = "†" in pc_markers.values()
    has_double_dagger = "‡" in pc_markers.values()
    show_markers = has_dagger or has_double_dagger

    def _page_footer(canvas: Any, _doc: Any) -> None:
        canvas.saveState()
        margin = _doc.leftMargin
        page_w = _doc.width + margin  # rightmost x of content
        
        y_sep = 12 * mm  
        y_text = y_sep - 4 * mm

        # Thin horizontal separator
        canvas.setStrokeColor(C_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(margin, y_sep, page_w, y_sep)

        # Legend text settings
        canvas.setFont("Helvetica", 7)
        x = margin

        # Critical Indicator
        canvas.setFillColor(C_DANGER)
        canvas.drawString(x, y_text, "●")
        canvas.setFillColor(C_SECONDARY)
        canvas.drawString(x + 2.5 * mm, y_text, "Critical")
        x += 20 * mm

        # Nominal Indicator
        canvas.setFillColor(C_SUCCESS)
        canvas.drawString(x, y_text, "●")
        canvas.setFillColor(C_SECONDARY)
        canvas.drawString(x + 2.5 * mm, y_text, "Nominal")
        x += 23 * mm

        # Suboptimal Indicator
        canvas.setFillColor(C_WARN)
        canvas.drawString(x, y_text, "●")
        canvas.setFillColor(C_SECONDARY)
        canvas.drawString(x + 2.5 * mm, y_text, "Suboptimal")
        x += 30 * mm

        # Hardware degradation markers section
        if show_markers:
            canvas.setFillColor(C_SECONDARY)
            if has_dagger:
                canvas.drawString(x, y_text, "†  Metric invalid")
                x += 30 * mm
            if has_double_dagger:
                canvas.drawString(x, y_text, "‡  Metric degraded")

        canvas.restoreState()

        # QR code in the top margin on every page.
        _draw_qr(canvas, _doc, _report_qr_url())

    doc.onFirstPage = _page_footer
    doc.onLaterPages = _page_footer
    doc.build(elems)
    return path
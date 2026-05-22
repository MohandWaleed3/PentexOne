import os
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from database import get_db, Device, Vulnerability
from models import ReportSummary

router = APIRouter(prefix="/reports", tags=["Reports"])


# ────────────────────────────────────────────────────────────
# Theme
# ────────────────────────────────────────────────────────────
BRAND_PRIMARY   = colors.HexColor("#0ea5e9")   # sky-500
BRAND_DARK      = colors.HexColor("#0f172a")   # slate-900
BRAND_ACCENT    = colors.HexColor("#7c3aed")   # violet-600
TEXT_DARK       = colors.HexColor("#1e293b")
TEXT_MUTED      = colors.HexColor("#64748b")
BG_LIGHT        = colors.HexColor("#f8fafc")
BG_SOFT         = colors.HexColor("#eef2f7")
BORDER          = colors.HexColor("#cbd5e1")

RISK_COLORS = {
    "RISK":    colors.HexColor("#dc2626"),
    "HIGH":    colors.HexColor("#dc2626"),
    "CRITICAL":colors.HexColor("#b91c1c"),
    "MEDIUM":  colors.HexColor("#f59e0b"),
    "LOW":     colors.HexColor("#0ea5e9"),
    "SAFE":    colors.HexColor("#16a34a"),
    "UNKNOWN": colors.HexColor("#64748b"),
}


def _risk_color(level: str):
    return RISK_COLORS.get((level or "UNKNOWN").upper(), TEXT_MUTED)


def _remediation_for(vuln_type: str) -> str:
    vt = (vuln_type or "").upper()
    if "TELNET" in vt or "FTP" in vt:
        return "Disable the service and use encrypted alternatives (SSH / SFTP)."
    if "CREDENTIALS" in vt:
        return "Change default passwords immediately to strong, unique passphrases."
    if "BLE_NO_PAIRING" in vt:
        return "Enable pairing 'Bonding' requirements in device settings if supported."
    if "MIFARE_DEFAULT" in vt:
        return "Migrate to MIFARE DESFire or update sector keys from factory defaults."
    if "SMB" in vt:
        return "Apply latest SMB patches, disable SMBv1, restrict exposure via firewall."
    if "RDP" in vt:
        return "Limit RDP to VPN, enforce Network Level Authentication, use strong passwords."
    if "HTTP" in vt and "HTTPS" not in vt:
        return "Enable HTTPS / TLS for all web traffic. Redirect HTTP to HTTPS."
    if "SSL" in vt or "TLS" in vt:
        return "Disable deprecated SSL/TLS versions and weak ciphers. Renew certificates."
    if "UPNP" in vt:
        return "Disable UPnP on the router unless strictly required."
    if "WEP" in vt or "WPA1" in vt:
        return "Upgrade Wi-Fi encryption to WPA2/WPA3."
    if "OPEN_NETWORK" in vt:
        return "Enable WPA2/WPA3 encryption and set a strong PSK."
    if "DEEP_SCAN_" in vt:
        return "Review the open service version, apply vendor patches, restrict via firewall."
    return "Apply latest firmware/patches and restrict service exposure with firewall rules."


# ────────────────────────────────────────────────────────────
# Page header / footer
# ────────────────────────────────────────────────────────────
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logo.png")


def _draw_page(canvas, doc):
    canvas.saveState()
    width, height = A4

    # Top bar (taller to fit larger logo)
    bar_h = 24 * mm
    canvas.setFillColor(BRAND_DARK)
    canvas.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)
    canvas.setFillColor(BRAND_PRIMARY)
    canvas.rect(0, height - bar_h - 1.5 * mm, width, 1.5 * mm, fill=1, stroke=0)

    # Logo (if available)
    if os.path.exists(LOGO_PATH):
        try:
            canvas.drawImage(
                LOGO_PATH,
                15 * mm, height - bar_h + 2 * mm,
                width=66 * mm, height=20 * mm,
                preserveAspectRatio=True, mask='auto'
            )
        except Exception:
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 14)
            canvas.drawString(20 * mm, height - 14 * mm, "PENTEX ONE")
    else:
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(20 * mm, height - 14 * mm, "PENTEX ONE")

    # Date on the right
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.white)
    canvas.drawRightString(width - 20 * mm, height - 14 * mm,
                           datetime.now().strftime("%B %d, %Y"))

    # Footer
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(20 * mm, 10 * mm,
                      "Confidential — Pentex One Security Audit")
    canvas.drawRightString(width - 20 * mm, 10 * mm,
                           f"Page {doc.page}")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 13 * mm, width - 20 * mm, 13 * mm)

    canvas.restoreState()


# ────────────────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────────────────
@router.get("/summary", response_model=ReportSummary)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Quick dashboard statistics."""
    total = db.query(Device).count()
    safe = db.query(Device).filter(Device.risk_level == "SAFE").count()
    medium = db.query(Device).filter(Device.risk_level == "MEDIUM").count()
    risk = db.query(Device).filter(Device.risk_level == "RISK").count()
    unknown = db.query(Device).filter(Device.risk_level == "UNKNOWN").count()

    return ReportSummary(
        total_devices=total,
        safe_count=safe,
        medium_count=medium,
        risk_count=risk,
        unknown_count=unknown,
        scan_time=datetime.utcnow()
    )


@router.get("/generate/pdf")
async def generate_pdf_report(db: Session = Depends(get_db)):
    """Generates a polished PDF report of devices, ports, and vulnerabilities."""
    os.makedirs("generated_reports", exist_ok=True)
    filename = (
        f"generated_reports/PentexOne_Security_Report_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )

    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=34 * mm, bottomMargin=18 * mm,
        title="Pentex One Security Audit Report",
        author="Pentex One"
    )

    base_styles = getSampleStyleSheet()
    styles = {
        "Body": ParagraphStyle("Body", parent=base_styles["Normal"],
                               fontSize=10, leading=14, textColor=TEXT_DARK),
        "Muted": ParagraphStyle("Muted", parent=base_styles["Normal"],
                                fontSize=9, leading=12, textColor=TEXT_MUTED),
        "MainTitle": ParagraphStyle("MainTitle", parent=base_styles["Heading1"],
                                    fontSize=22, leading=26, spaceAfter=4,
                                    textColor=BRAND_DARK),
        "SubTitle": ParagraphStyle("SubTitle", parent=base_styles["Normal"],
                                   fontSize=11, leading=14, textColor=TEXT_MUTED,
                                   spaceAfter=14),
        "Section": ParagraphStyle("Section", parent=base_styles["Heading2"],
                                  fontSize=14, leading=18, spaceBefore=18,
                                  spaceAfter=8, textColor=BRAND_DARK,
                                  borderPadding=(0, 0, 4, 0)),
        "DeviceTitle": ParagraphStyle("DeviceTitle", parent=base_styles["Heading3"],
                                      fontSize=11, leading=14, spaceBefore=10,
                                      spaceAfter=4, textColor=BRAND_PRIMARY),
        "VulnTitle": ParagraphStyle("VulnTitle", parent=base_styles["Normal"],
                                    fontSize=10, leading=13, spaceBefore=4,
                                    textColor=TEXT_DARK, fontName="Helvetica-Bold"),
        "VulnDesc": ParagraphStyle("VulnDesc", parent=base_styles["Normal"],
                                   fontSize=9.5, leading=13, textColor=TEXT_DARK,
                                   leftIndent=10),
        "Remediation": ParagraphStyle("Remediation", parent=base_styles["Normal"],
                                      fontSize=9.5, leading=13,
                                      textColor=colors.HexColor("#15803d"),
                                      leftIndent=10, spaceAfter=6),
    }

    elements = []

    # ── Title block ──────────────────────────────────────────
    elements.append(Paragraph("Security Audit Report", styles["MainTitle"]))
    elements.append(Paragraph(
        f"Generated on {datetime.now().strftime('%B %d, %Y · %H:%M')}",
        styles["SubTitle"]
    ))

    # ── Executive Summary as stat cards ──────────────────────
    devices = db.query(Device).order_by(Device.risk_score.desc()).all()
    total = len(devices)
    risk_count = sum(1 for d in devices if d.risk_level == "RISK")
    med_count = sum(1 for d in devices if d.risk_level == "MEDIUM")
    safe_count = sum(1 for d in devices if d.risk_level == "SAFE")
    vuln_total = db.query(Vulnerability).count()

    summary_cards = [[
        Paragraph(f"<b>{total}</b>", styles["Body"]),
        Paragraph(f"<b>{risk_count}</b>", styles["Body"]),
        Paragraph(f"<b>{med_count}</b>", styles["Body"]),
        Paragraph(f"<b>{safe_count}</b>", styles["Body"]),
        Paragraph(f"<b>{vuln_total}</b>", styles["Body"]),
    ], [
        Paragraph("Devices", styles["Muted"]),
        Paragraph("High Risk", styles["Muted"]),
        Paragraph("Medium", styles["Muted"]),
        Paragraph("Safe", styles["Muted"]),
        Paragraph("Vulnerabilities", styles["Muted"]),
    ]]

    card_widths = [35 * mm] * 5
    cards = Table(summary_cards, colWidths=card_widths, rowHeights=[16, 12])
    cards.setStyle(TableStyle([
        ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), BG_SOFT),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, BORDER),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('FONTSIZE', (0, 1), (-1, 1), 8),
        ('TEXTCOLOR', (1, 0), (1, 0), RISK_COLORS["RISK"]),
        ('TEXTCOLOR', (2, 0), (2, 0), RISK_COLORS["MEDIUM"]),
        ('TEXTCOLOR', (3, 0), (3, 0), RISK_COLORS["SAFE"]),
        ('TEXTCOLOR', (4, 0), (4, 0), BRAND_ACCENT),
    ]))
    elements.append(cards)
    elements.append(Spacer(1, 8))

    summary_text = (
        f"The audit scanned <b>{total}</b> devices on the target network. "
        f"<b>{risk_count}</b> high-risk and <b>{med_count}</b> medium-risk devices were "
        f"identified, with <b>{vuln_total}</b> vulnerabilities catalogued. "
        f"High-risk devices require immediate remediation."
    )
    elements.append(Paragraph(summary_text, styles["Body"]))

    # ── Device Inventory ─────────────────────────────────────
    elements.append(Paragraph("Discovered Devices Inventory", styles["Section"]))

    header = ["IP / MAC", "Hostname", "Protocol", "Open Ports", "Risk", "Score"]
    data = [header]

    for d in devices:
        ports = (d.open_ports or "").strip()
        if not ports:
            ports_cell = "—"
        else:
            # Wrap long port lists
            port_list = ports.split(",")
            if len(port_list) > 8:
                ports_cell = ", ".join(port_list[:8]) + f"  (+{len(port_list)-8})"
            else:
                ports_cell = ", ".join(port_list)

        data.append([
            Paragraph(f"<b>{d.ip}</b><br/><font size=7 color='#64748b'>{d.mac or ''}</font>",
                      styles["Body"]),
            Paragraph((d.hostname or "Unknown")[:30], styles["Body"]),
            d.protocol or "—",
            Paragraph(f"<font size=8>{ports_cell}</font>", styles["Body"]),
            d.risk_level or "UNKNOWN",
            str(round(d.risk_score or 0, 1)),
        ])

    inv_table = Table(
        data,
        colWidths=[33 * mm, 30 * mm, 18 * mm, 55 * mm, 18 * mm, 14 * mm],
        repeatRows=1
    )
    inv_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 9),
        ('ALIGN',      (0, 0), (-1, 0), 'LEFT'),
        ('ALIGN',      (4, 0), (5, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
    ])

    for i, d in enumerate(devices, start=1):
        bg = BG_LIGHT if i % 2 == 1 else colors.white
        inv_style.add('BACKGROUND', (0, i), (-1, i), bg)
        inv_style.add('TEXTCOLOR', (4, i), (4, i), _risk_color(d.risk_level))
        inv_style.add('FONTNAME', (4, i), (4, i), 'Helvetica-Bold')

    inv_table.setStyle(inv_style)
    elements.append(inv_table)

    # ── Vulnerability Analysis ───────────────────────────────
    devices_with_vulns = [d for d in devices if d.vulnerabilities]
    if devices_with_vulns:
        elements.append(Paragraph("Vulnerability Analysis & Remediation",
                                  styles["Section"]))

        for d in devices_with_vulns:
            block = [
                Paragraph(
                    f"{d.ip} &nbsp;·&nbsp; <font color='#64748b'>{d.hostname or 'Unknown'}</font>",
                    styles["DeviceTitle"]
                )
            ]
            for v in d.vulnerabilities:
                sev = (v.severity or "MEDIUM").upper()
                sev_color = _risk_color(sev).hexval()[2:]  # strip 0x
                port_tag = f" · port {v.port}" if v.port else ""
                title = (
                    f"<font color='#{sev_color}'><b>● {sev}</b></font> &nbsp;"
                    f"{v.vuln_type}{port_tag}"
                )
                block.append(Paragraph(title, styles["VulnTitle"]))
                if v.description:
                    block.append(Paragraph(v.description, styles["VulnDesc"]))
                block.append(Paragraph(
                    f"<b>Remediation:</b> {_remediation_for(v.vuln_type)}",
                    styles["Remediation"]
                ))
            elements.append(KeepTogether(block))

    # ── RFID Section ─────────────────────────────────────────
    from database import RFIDCard
    rfid_cards = db.query(RFIDCard).order_by(RFIDCard.last_seen.desc()).all()
    if rfid_cards:
        elements.append(Paragraph("Access Control (RFID / NFC) Audit",
                                  styles["Section"]))

        rfid_data = [["UID / Identifier", "Tag Technology", "Risk Rating"]]
        for card in rfid_cards:
            rfid_data.append([card.uid, card.card_type, card.risk_level])

        rt = Table(rfid_data, colWidths=[70 * mm, 55 * mm, 35 * mm], repeatRows=1)
        rt_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_ACCENT),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 9),
            ('ALIGN',      (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN',      (2, 0), (2, -1), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ])
        for i, card in enumerate(rfid_cards, start=1):
            bg = BG_LIGHT if i % 2 == 1 else colors.white
            rt_style.add('BACKGROUND', (0, i), (-1, i), bg)
            rt_style.add('TEXTCOLOR', (2, i), (2, i), _risk_color(card.risk_level))
            rt_style.add('FONTNAME', (2, i), (2, i), 'Helvetica-Bold')
        rt.setStyle(rt_style)
        elements.append(rt)

    # ── Closing note ─────────────────────────────────────────
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(
        "<i>This report is generated automatically by Pentex One. "
        "Findings should be validated by a qualified security professional "
        "before remediation.</i>",
        styles["Muted"]
    ))

    doc.build(elements, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return FileResponse(
        path=filename,
        filename="PentexOne_Security_Report.pdf",
        media_type="application/pdf"
    )

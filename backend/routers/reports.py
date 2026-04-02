import os
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from database import get_db, Device, Vulnerability
from models import ReportSummary

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary", response_model=ReportSummary)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """يرجع إحصائيات سريعة للـ Dashboard"""
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
    """Generates an improved PDF report for devices and vulnerabilities"""
    
    os.makedirs("generated_reports", exist_ok=True)
    filename = f"generated_reports/PentexOne_Security_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(name='MainTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=10, textColor=colors.HexColor("#38bdf8"), alignment=0))
    styles.add(ParagraphStyle(name='SubTitle', parent=styles['Normal'], fontSize=12, spaceAfter=20, textColor=colors.grey))
    styles.add(ParagraphStyle(name='SectionHeader', parent=styles['Heading2'], fontSize=16, spaceBefore=20, spaceAfter=10, textColor=colors.HexColor("#1e293b")))
    styles.add(ParagraphStyle(name='Remediation', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor("#334155"), leading=14, leftIndent=10))

    elements = []
    
    # Header
    elements.append(Paragraph("Pentex One — Security Audit Report", styles["MainTitle"]))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y - %H:%M:%S')}", styles["SubTitle"]))
    elements.append(Spacer(1, 10))
    
    # Executive Summary
    elements.append(Paragraph("Executive Summary", styles["SectionHeader"]))
    total = db.query(Device).count()
    risk_count = db.query(Device).filter(Device.risk_level == "RISK").count()
    med_count = db.query(Device).filter(Device.risk_level == "MEDIUM").count()
    
    summary_text = f"The security audit discovered a total of <b>{total}</b> devices. Among these, <b>{risk_count}</b> were identified as high risk and <b>{med_count}</b> as medium risk. Immediate action is recommended for devices marked in red."
    elements.append(Paragraph(summary_text, styles["Normal"]))
    elements.append(Spacer(1, 20))
    
    # Device Table
    elements.append(Paragraph("Discovered Devices Inventory", styles["SectionHeader"]))
    devices = db.query(Device).order_by(Device.risk_score.desc()).all()
    
    data = [["IP/MAC", "Hostname", "Protocol", "Risk Level", "Score"]]
    for d in devices:
        data.append([
            f"{d.ip}\n{d.mac or ''}",
            d.hostname[:20],
            d.protocol,
            d.risk_level,
            str(d.risk_score)
        ])
        
    t = Table(data, colWidths=[130, 140, 80, 100, 60])
    
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,1), (-1,-1), 9),
    ])
    
    for i, row in enumerate(data[1:], start=1):
        if row[3] == "RISK":
            t_style.add('TEXTCOLOR', (3,i), (3,i), colors.red)
        elif row[3] == "MEDIUM":
            t_style.add('TEXTCOLOR', (3,i), (3,i), colors.orange)
        elif row[3] == "SAFE":
            t_style.add('TEXTCOLOR', (3,i), (3,i), colors.green)
            
    t.setStyle(t_style)
    elements.append(t)
    
    # Detailed Vulnerabilities & Remediation
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("Vulnerability Analysis & Remediation", styles["SectionHeader"]))
    
    for d in devices:
        if d.vulnerabilities:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(f"Device: {d.ip} ({d.hostname})", styles["Heading3"]))
            
            for v in d.vulnerabilities:
                elements.append(Paragraph(f"• <b>{v.vuln_type}</b> ({v.severity})", styles["Normal"]))
                elements.append(Paragraph(f"<i>Issue:</i> {v.description}", styles["Normal"]))
                
                # Remediation logic
                guide = "Contact vendor for updates."
                if "TELNET" in v.vuln_type or "FTP" in v.vuln_type:
                    guide = "Disable the service and use encrypted alternatives (SSH/SFTP)."
                elif "CREDENTIALS" in v.vuln_type:
                    guide = "Change default passwords immediately to a strong, unique passphrase."
                elif "BLE_NO_PAIRING" in v.vuln_type:
                    guide = "Enable pairing 'Bonding' requirements in device settings if supported."
                elif "MIFARE_DEFAULT" in v.vuln_type:
                    guide = "Migrate to MIFARE DESFire or update sector keys from factory defaults."

                elements.append(Paragraph(f"<b>Remediation:</b> {guide}", styles["Remediation"]))
                elements.append(Spacer(1, 5))

    # RFID Section
    from database import RFIDCard
    rfid_cards = db.query(RFIDCard).order_by(RFIDCard.last_seen.desc()).all()
    if rfid_cards:
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("Access Control (RFID/NFC) Audit", styles["SectionHeader"]))
        rfid_data = [["UID / Identifier", "Tag Technology", "Risk Rating"]]
        for card in rfid_cards:
            rfid_data.append([card.uid, card.card_type, card.risk_level])
            
        rt = Table(rfid_data, colWidths=[180, 180, 100])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7c3aed")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        elements.append(rt)

    doc.build(elements)
    return FileResponse(path=filename, filename="PentexOne_Security_Report.pdf", media_type="application/pdf")

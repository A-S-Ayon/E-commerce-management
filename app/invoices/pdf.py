from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def generate_invoice_pdf(order: dict, items: list[dict], invoice_number: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Invoice {invoice_number}", styles["Title"]))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Order ID: {order['id']}", styles["Normal"]))
    elements.append(Paragraph(f"Date: {order['created_at'].strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    elements.append(Paragraph(f"Status: {order['status']}", styles["Normal"]))
    elements.append(Spacer(1, 16))

    table_data = [["Product", "Qty", "Unit Price", "Line Total"]]
    for item in items:
        table_data.append([
            item["name"],
            str(item["quantity"]),
            f"${item['unit_price']:.2f}",
            f"${item['line_total']:.2f}",
        ])
    table_data.append(["", "", "Grand Total", f"${order['total_amount']:.2f}"])

    table = Table(table_data, colWidths=[220, 60, 90, 90])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


#just checking some of git

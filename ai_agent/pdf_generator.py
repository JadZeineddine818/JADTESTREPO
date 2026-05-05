from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import uuid
import textwrap
import datetime
from zoneinfo import ZoneInfo

def generate_pdf(report_text):

    os.makedirs("reports", exist_ok=True)

    report_id = str(uuid.uuid4())[:8]
    file_path = f"reports/report_{report_id}.pdf"

    c = canvas.Canvas(file_path, pagesize=letter)

    width, height = letter

    left_margin = 60
    right_margin = width - 60
    y = height - 70

    max_chars = 95
    page_number = 1

    # -------------------------
    # FOOTER FUNCTION
    # -------------------------
    def draw_footer():
        c.setFont("Helvetica-Oblique", 9)
        c.drawRightString(right_margin, 40, f"Page {page_number}")

    # -------------------------
    # HEADER FUNCTION 
    # -------------------------
    def draw_header():
        nonlocal y
        
        c.setFont("Helvetica-Bold", 14)
        c.drawString(left_margin, y, "Security Assessment Report")
        y -= 30

        c.setFont("Helvetica", 10)
        date = datetime.datetime.now(ZoneInfo("Asia/Beirut")).strftime("%Y-%m-%d %H:%M")

        c.drawString(left_margin, y, f"Generated: {date}")
        y -= 15

        c.drawString(left_margin, y, f"Report ID: {report_id}")
        y -= 25

        c.line(left_margin, y, right_margin, y)
        y -= 20

    # draw header on first page
    draw_header()

    # -------------------------
    # CONTENT
    # -------------------------
    lines = report_text.split("\n")

    for raw_line in lines:

        line = raw_line.strip()

        if not line:
            y -= 10
            continue

        # remove markdown artifacts
        line = line.replace("**", "")
        line = line.replace("`", "")
        line = line.replace("---", "")
        line = line.replace("-", "")
        line = line.replace("python", "")

        # detect headings
        if line.startswith("###"):
            text = line.replace("###", "").strip()
            c.setFont("Helvetica-Bold", 13)
            y -= 5

        elif line.startswith("##"):
            text = line.replace("##", "").strip()
            c.setFont("Helvetica-Bold", 14)
            y -= 8
            c.line(left_margin, y, right_margin, y)
            y -= 10

        elif line.startswith("#"):
            text = line.replace("#", "").strip()
            c.setFont("Helvetica-Bold", 16)
            y -= 10

        else:
            text = line
            c.setFont("Helvetica", 11)

        wrapped = textwrap.wrap(text, max_chars)

        for w in wrapped:

            c.drawString(left_margin, y, w)
            y -= 15

            # page break
            if y < 70:

                draw_footer()
                c.showPage()

                page_number += 1

                y = height - 70
                

        y -= 4

    # final footer
    draw_footer()

    c.save()

    return file_path
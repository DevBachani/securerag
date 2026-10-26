"""Generate the 3 table PDFs in the Acme corpus.

The corpus is mostly Markdown, but three documents are PDFs with tables so that
later phases exercise real PDF/table parsing (pymupdf4llm in Phase 3):

  - hr/salary_bands_fy27.pdf
  - finance/q2_budget_fy27.pdf
  - finance/expense_approval_limits.pdf

Amounts use the ASCII prefix "INR" rather than the Rupee glyph, because fpdf2's
built-in core fonts are Latin-1 and cannot render the U+20B9 rupee symbol.

Run:  uv run python scripts/make_pdfs.py
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

# Corpus root; PDFs are written under it at the paths used in manifest.json.
CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"


def _new_pdf(title: str, subtitle: str) -> FPDF:
    """Return a PDF with a title block ready for a table."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, subtitle, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    return pdf


def _write_table(pdf: FPDF, rows: list[list[str]]) -> None:
    """Render a bordered table; the first row is treated as the header."""
    pdf.set_font("Helvetica", "", 10)
    with pdf.table() as table:
        for row in rows:
            table.row(row)


def build_salary_bands() -> Path:
    """Salary bands by level (confidential HR document)."""
    pdf = _new_pdf(
        "Salary Bands FY27",
        "Confidential - HR and Leadership only. Amounts in INR lakh per annum (LPA).",
    )
    rows = [
        ["Level", "Minimum (LPA)", "Midpoint (LPA)", "Maximum (LPA)"],
        ["L1", "6.0", "7.5", "9.0"],
        ["L2", "9.0", "11.5", "14.0"],
        ["L3", "14.0", "18.0", "22.0"],
        ["L4", "22.0", "28.0", "34.0"],
        ["L5", "34.0", "42.0", "50.0"],
        ["L6", "50.0", "62.0", "75.0"],
        ["L7", "75.0", "92.0", "110.0"],
    ]
    _write_table(pdf, rows)
    out = CORPUS / "hr" / "salary_bands_fy27.pdf"
    pdf.output(str(out))
    return out


def build_q2_budget() -> Path:
    """Q2 FY27 departmental budget (confidential finance document)."""
    pdf = _new_pdf(
        "Q2 FY27 Budget",
        "Confidential - Finance and Leadership only. Amounts in INR crore.",
    )
    rows = [
        ["Department", "Budget (INR crore)", "Share of total"],
        ["Engineering", "18", "50.0%"],
        ["Sales", "9", "25.0%"],
        ["Marketing", "5", "13.9%"],
        ["G&A", "4", "11.1%"],
        ["Total", "36", "100%"],
    ]
    _write_table(pdf, rows)
    out = CORPUS / "finance" / "q2_budget_fy27.pdf"
    pdf.output(str(out))
    return out


def build_expense_limits() -> Path:
    """Single-transaction expense approval limits by role."""
    pdf = _new_pdf(
        "Expense Approval Limits",
        "Confidential - Finance and Leadership only. Single-transaction limits in INR.",
    )
    rows = [
        ["Role", "Approval limit (INR)"],
        ["Employee", "10,000"],
        ["Team Lead", "25,000"],
        ["Manager", "50,000"],
        ["Director", "2,00,000"],
        ["VP", "10,00,000"],
        ["CFO", "Unlimited"],
    ]
    _write_table(pdf, rows)
    out = CORPUS / "finance" / "expense_approval_limits.pdf"
    pdf.output(str(out))
    return out


def main() -> None:
    """Generate all three PDFs and print where they landed."""
    for builder in (build_salary_bands, build_q2_budget, build_expense_limits):
        path = builder()
        print(f"wrote {path.relative_to(CORPUS.parent.parent)}")


if __name__ == "__main__":
    main()

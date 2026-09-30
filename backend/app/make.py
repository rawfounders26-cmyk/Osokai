"""Artifact builders — Osok-AI DELIVERS files, not just words.
Everything lands in workspace/ (visible in Files tab + Command Port)."""
import json, os, subprocess, sys

try:
    from app.paths import ws as _pws
except ImportError:
    from paths import ws as _pws

WS = _pws()

def _path(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", ".", " ")).strip() or "osokai-file"
    return os.path.join(WS, safe)

ACCENT = (0x5B, 0x5B, 0xD6)
DARK = (0x1A, 0x1A, 0x2E)

def _style_title(shape, size=32):
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt
    for p in shape.text_frame.paragraphs:
        p.alignment = PP_ALIGN.LEFT
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.bold = True
            r.font.color.rgb = RGBColor(*DARK)

def make_pptx(title: str, slides_json: str) -> str:
    """Styled deck: accent title slide, section headers, tidy bullets, footer + slide numbers."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Pt, Inches
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.33), Inches(7.5)
    # title slide with accent bar
    t = prs.slides.add_slide(prs.slide_layouts[6])
    bar = t.shapes.add_shape(1, Inches(0.7), Inches(1.2), Inches(0.12), Inches(3.4))
    bar.fill.solid()
    bar.fill.fore_color.rgb = RGBColor(*ACCENT)
    bar.line.fill.background()
    tx = t.shapes.add_textbox(Inches(1.1), Inches(1.2), Inches(11), Inches(2.4))
    tx.text_frame.word_wrap = True
    tx.text_frame.paragraphs[0].text = title
    _style_title(tx, 40)
    sub = t.shapes.add_textbox(Inches(1.1), Inches(3.8), Inches(11), Inches(1))
    sub.text_frame.paragraphs[0].text = "Prepared by Osok-AI"
    sub.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
    sub.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x8A, 0x8A, 0x96)
    try:
        slides = json.loads(slides_json) if isinstance(slides_json, str) else slides_json
    except Exception:
        slides = []
    for idx, s in enumerate(slides, start=2):
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        bar = sl.shapes.add_shape(1, Inches(0.7), Inches(0.5), Inches(0.1), Inches(1.1))
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor(*ACCENT)
        bar.line.fill.background()
        hd = sl.shapes.add_textbox(Inches(1.0), Inches(0.4), Inches(11.5), Inches(1.2))
        hd.text_frame.word_wrap = True
        hd.text_frame.paragraphs[0].text = s.get("heading", "")
        _style_title(hd, 30)
        tf = sl.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(11.5), Inches(4.4)).text_frame
        tf.word_wrap = True
        first = True
        for b in s.get("bullets", [])[:6]:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.text = str(b)
            p.level = 0
            p.space_after = Pt(8)
            p.runs[0].font.size = Pt(20)
        ft = sl.shapes.add_textbox(Inches(1.0), Inches(6.7), Inches(11.5), Inches(0.5))
        run = ft.text_frame.paragraphs[0].add_run()
        run.text = f"Osok-AI  •  {idx}"
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x8A, 0x8A, 0x96)
    fp = _path(title[:40] + ".pptx")
    prs.save(fp)
    return fp

def _num(v):
    try:
        return float(str(v).replace(",", "").replace("₹", "").replace("$", "").strip())
    except Exception:
        return None


def _cell(c):
    import re as _re
    if isinstance(c, (int, float)):
        return c
    if isinstance(c, str) and _re.match(r"^[\d₹$,\.\s-]+$", c) and _num(c) is not None:
        return _num(c)
    return c

def make_xlsx(name: str, sheets_json: str) -> str:
    """PowerBI-style: dashboard sheet + banded tables + conditional scales + charts."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.chart import BarChart, LineChart, Reference
    ACC, BAND = "5B5BD6", "F1F1F8"
    try:
        sheets = json.loads(sheets_json) if isinstance(sheets_json, str) else sheets_json
    except Exception:
        sheets = {"Sheet1": []}
    sheets = sheets or {"Sheet1": []}
    wb = Workbook()
    dash = wb.active
    dash.title = "Dashboard"
    dash["A1"] = name.replace(".xlsx", "")
    dash["A1"].font = Font(bold=True, size=18, color=ACC)
    dash["A2"] = "Prepared by Osok-AI"
    dash["A2"].font = Font(italic=True, color="8A8A96")
    thin = Side(style="thin", color="D9D9E3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for sname, rows in sheets.items():
        ws = wb.create_sheet(str(sname)[:30])
        data = rows or []
        for r in data:
            ws.append([_cell(c) for c in r])
        if ws.max_row < 1:
            continue
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=ACC)
            c.alignment = Alignment(horizontal="center")
            c.border = border
        for row in ws.iter_rows(min_row=2):
            for idx, c in enumerate(row):
                c.border = border
                if idx == 0:
                    c.font = Font(bold=True)
                if row[0].row % 2 == 0:
                    c.fill = PatternFill("solid", fgColor=BAND)
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = 18
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        # numeric columns get a color scale + totals row
        numcols = []
        for j in range(1, ws.max_column + 1):
            vals = [ws.cell(row=i, column=j).value for i in range(2, ws.max_row + 1)]
            if vals and all(isinstance(v, (int, float)) for v in vals):
                numcols.append(j)
        if ws.max_row >= 2 and numcols:
            for j in numcols:
                col = ws.cell(row=1, column=j).column_letter
                ws.conditional_formatting.add(f"{col}2:{col}{ws.max_row}",
                    ColorScaleRule(start_type="min", start_color="F8696B",
                                   mid_type="percentile", mid_value=50, mid_color="FFEB84",
                                   end_type="max", end_color="63BE7B"))
            tr = ws.max_row + 1
            ws.cell(row=tr, column=1).value = "TOTAL"
            ws.cell(row=tr, column=1).font = Font(bold=True)
            for j in numcols:
                col = ws.cell(row=1, column=j).column_letter
                ws.cell(row=tr, column=j).value = f"=SUM({col}2:{col}{tr - 1})"
                ws.cell(row=tr, column=j).font = Font(bold=True)
        # chart on dashboard: first numeric column of first data sheet
        if sname == list(sheets.keys())[0] and numcols and ws.max_row >= 3:
            ch = BarChart()
            ch.title = f"{sname} — overview"
            ch.style = 10
            data_ref = Reference(ws, min_col=numcols[0], min_row=1, max_row=min(ws.max_row, 12))
            cats = Reference(ws, min_col=1, min_row=2, max_row=min(ws.max_row, 12))
            ch.add_data(data_ref, titles_from_data=True)
            ch.set_categories(cats)
            ch.height, ch.width = 8, 15
            dash.add_chart(ch, "A4")
    # dashboard KPIs: sheet count + row counts
    r = 16
    dash.cell(row=r, column=1).value = "Sheets"
    dash.cell(row=r, column=2).value = len(sheets)
    for sname in sheets:
        r += 1
        dash.cell(row=r, column=1).value = sname
    fp = _path(name if name.endswith(".xlsx") else name + ".xlsx")
    wb.save(fp)
    return fp

def write_file(name: str, content: str) -> str:
    fp = _path(name)
    open(fp, "w", encoding="utf-8").write(content)
    return fp

def make_dir(name: str) -> str:
    """Create a folder in workspace/ (same store the mobile Files screen shows)."""
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip() or "osokai-folder"
    fp = os.path.join(WS, safe)
    os.makedirs(fp, exist_ok=True)
    return fp

def run_tests(target: str = "") -> str:
    """Run pytest on workspace code. target: file or '' for all."""
    t = _path(target) if target else WS
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", t, "-q"], capture_output=True, text=True, timeout=120)
        return ((r.stdout or "") + ("\n" + r.stderr if r.stderr else ""))[:3000]
    except subprocess.TimeoutExpired:
        return "(tests timed out)"
    except Exception as e:
        return f"(test error: {e})"

def fetch_url(url: str, max_chars: int = 6000) -> str:
    import re
    import httpx
    try:
        from app.system_tools import clean_url
    except ImportError:
        from system_tools import clean_url
    url = clean_url(url)
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25, follow_redirects=True)
        txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S | re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        return re.sub(r"\s+", " ", txt)[:max_chars]
    except Exception as e:
        return f"(fetch error: {e})"

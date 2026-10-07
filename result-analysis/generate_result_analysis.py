#!/usr/bin/env python3
"""Generate a Result Analysis CSV (matching RESULT ANALYSIS FORMAT.pdf) for every
exam sheet found in each class folder.

Layout of the output is taken verbatim from result_analysis_format.csv.
"""

import csv
import os
import re

import openpyxl

ROOT = os.path.dirname(os.path.abspath(__file__))

CLASSES = ["IX A", "IX G", "VII A", "X C", "X F", "X H", "X I", "XI D"]
SESSION = "2026-27"

# Only the Half Yearly exam is reported; PT / Pre-Board / Annual sheets are skipped.
WANTED_EXAMS = ("HALF-YEARLY",)

# Sheets whose own title does not name the exam but which are the class's
# half-yearly master sheet.
SHEET_EXAM_OVERRIDE = {
    ("X C", "SHEET1"): "HALF-YEARLY",
    ("X F", "SHEET1"): "HALF-YEARLY",
}

# Class teachers named on the sheet top (e.g. "C.T. - John Das") are picked up
# automatically; classes whose master does not carry the name are filled from
# this override instead.
CLASS_TEACHER_OVERRIDE = {
    "IX G": "ARVIND PATHAK",
}

HEADER = [
    "exam_name", "exam_type", "class_section", "exam_period_from", "exam_period_to",
    "class_strength", "class_teacher_name", "subject", "highest_marks", "average_marks",
    "less_than_40", "40_to_50", "50_to_60", "60_to_75", "75_to_90", "more_than_90",
    "subject_teacher", "no_students_passed", "detained", "advised_for_improvement", "date",
]

FORMAT_SUBJECTS = [
    "English", "Hindi", "Sanskrit", "Mathematics", "Science", "Physics", "Chemistry",
    "Biology", "Social Sc.", "Accountancy", "B. St.", "Economics", "Physical Edu.",
    "A.I.",
]
SPARE_ROWS = 1

BANDS = (
    "less_than_40", "40_to_50", "50_to_60", "60_to_75", "75_to_90", "more_than_90",
)

CANON = {
    "ENG": "English", "ENGLISH": "English",
    "HINDI": "Hindi",
    "SANSK": "Sanskrit", "SNK": "Sanskrit", "SANK": "Sanskrit",
    "MATHS": "Mathematics", "SCI": "Science", "SCIENCE": "Science",
    "SSC": "Social Sc.", "S.SC.": "Social Sc.", "S SC": "Social Sc.", "S.SC": "Social Sc.",
    "S. SCI": "Social Sc.",
    "ACC": "Accountancy", "BST": "B. St.", "ECO": "Economics",
    "PHY. EDU": "Physical Edu.",
    "AI": "A.I.", "A I": "A.I.",
}

# Per-subject maxima recovered from each sheet's own TOTAL / PER formula
# (see report below). Keys are subj_key(header). Only subjects that feed the
# sheet's TOTAL are listed, plus A.I., which every IX/X/XI sheet carries but
# deliberately leaves outside the TOTAL / %AGE formula.
MAXMARKS = {
    ("IX A", "PT-1"): {"ENG": 40, "HINDI": 40, "MATHS": 40, "SCI": 40, "SSC": 40},
    ("IX A", "PT-2"): {"ENG": 40, "HINDI": 40, "MATHS": 40, "SCI": 40, "SSC": 40},
    ("IX A", "HALF-YEARLY"): {
        "ENG": 80, "HINDI": 80, "MATHS": 80, "SCI": 80, "SSC": 80, "AI": 50,
    },
    ("IX G", "HALF-YEARLY"): {
        "ENG": 80, "SNK": 80, "MATHS": 80, "S.SC": 80, "SCI": 80, "AI": 50,
    },
    ("VII A", "HALF-YEARLY"): {
        "ENG": 70, "HINDI": 70, "MATHS": 70, "SCIENCE": 70, "S.SC.": 70, "SANSK": 70,
    },
    ("X C", "HALF-YEARLY"): {
        "ENGLISH": 80, "HINDI": 80, "MATHS": 80, "SCIENCE": 80, "S. SCI": 80, "A I": 50,
    },
    ("X F", "HALF-YEARLY"): {
        "ENG": 80, "SANK": 80, "MATHS": 80, "SCI": 80, "S SC": 80, "AI": 100,
    },
    ("X H", "HALF-YEARLY"): {
        "ENG": 80, "HINDI": 80, "MATHS": 80, "SCI": 80, "SSC": 80, "AI": 50,
    },
    ("X H", "PT-1"): {"ENG": 40, "HINDI": 40, "MATHS": 40, "SCI": 40, "SSC": 40, "AI": 40},
    ("X I", "HALF-YEARLY"): {
        "ENG": 80, "HINDI": 80, "MATHS": 80, "SCI": 80, "SSC": 80, "AI": 50,
    },
    ("X I", "PT-1"): {"ENG": 40, "HINDI": 40, "MATHS": 40, "SCI": 40, "SSC": 40, "AI": 40},
    ("XI D", "HALF-YEARLY"): {
        "ENG": 80, "ACC": 80, "BST": 80, "ECO": 80, "PHY. EDU": 70, "AI": 50,
    },
}

PER_HEADERS = ("PER", "% AGE", "%AGE", "%")

EXAM_PATTERNS = [
    (re.compile(r"PT\s*-?\s*([1-4])"), lambda m: "PT-%s" % m.group(1)),
    (re.compile(r"HALF\s*[-\s]*YEARLY"), lambda m: "HALF-YEARLY"),
    (re.compile(r"PRE\s*[-\s]*BOARD"), lambda m: "PRE-BOARD"),
    (re.compile(r"ANNUAL"), lambda m: "ANNUAL"),
]

PASS_MARK = 33.0
IMPROVE_MARK = 40.0


def norm(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().upper()


def subj_key(header):
    """Header reduced to the key used in MAXMARKS / CANON: upper-case with
    any parenthesised max-marks note (e.g. 'English (80)', 'A I (50)') removed.
    """
    return re.sub(r"\s*\(.*?\)", "", norm(header)).strip()


def exam_type_for(section, sheet_title):
    override = SHEET_EXAM_OVERRIDE.get((section, norm(sheet_title)))
    return override if override else detect_exam_type(sheet_title)


def is_id_header(header):
    n = norm(header)
    if "NAME" in n or "ADM" in n:
        return True
    if "ROLL" in n:
        return True
    if n.startswith("R") and "NO" in n:
        return True
    return False


def detect_exam_type(sheet_title):
    title = norm(sheet_title)
    for pattern, build in EXAM_PATTERNS:
        match = pattern.search(title)
        if match:
            return build(match)
    return None


def find_header_row(ws):
    for row in range(1, 7):
        for col in range(1, ws.max_column + 1):
            if norm(ws.cell(row=row, column=col).value) in (
                "ROLL", "R. NO.", "ADMNO", "ADM.NO.", "ADM NO", "ADM. NO."
            ):
                return row
    return None


def class_teacher_from_sheet(ws):
    for row in range(1, 5):
        for col in range(1, ws.max_column + 1):
            value = ws.cell(row=row, column=col).value
            if not isinstance(value, str):
                continue
            match = re.search(r"C\.?\s*T\.?\s*[:\-]\s*([A-Za-z .'\-]+)", value, re.I)
            if match:
                name = match.group(1).strip(" .-")
                name = re.split(r"\s{3,}", name)[0].strip()
                if name:
                    return name.upper()
    return ""


def cls_teacher(section):
    return CLASS_TEACHER_OVERRIDE.get(section, "")


def numeric(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def band_counts(percentages):
    return {
        "less_than_40": sum(1 for p in percentages if p < 40),
        "40_to_50": sum(1 for p in percentages if 40 <= p < 50),
        "50_to_60": sum(1 for p in percentages if 50 <= p < 60),
        "60_to_75": sum(1 for p in percentages if 60 <= p < 75),
        "75_to_90": sum(1 for p in percentages if 75 <= p <= 90),
        "more_than_90": sum(1 for p in percentages if p > 90),
    }


def analyse_sheet(ws, section, exam_type):
    hdr_row = find_header_row(ws)
    if hdr_row is None:
        raise RuntimeError("header row not found in %r" % ws.title)

    headers = []
    for col in range(1, ws.max_column + 1):
        value = ws.cell(row=hdr_row, column=col).value
        if value not in (None, ""):
            headers.append((col, str(value)))

    total_col = next((c for c, h in headers if norm(h) == "TOTAL"), None)
    if total_col is None:
        raise RuntimeError("TOTAL column not found in %r" % ws.title)
    per_col = next((c for c, h in headers if norm(h) in PER_HEADERS), None)
    name_col = next((c for c, h in headers if "NAME" in norm(h)), None)

    subject_cols = [(c, h) for c, h in headers if c < total_col and not is_id_header(h)]
    maxima = MAXMARKS[(section, exam_type)]
    graded_cols = [(c, h) for c, h in subject_cols if subj_key(h) in maxima]

    students = []
    for row in range(hdr_row + 1, ws.max_row + 1):
        name = ws.cell(row=row, column=name_col).value
        if name in (None, ""):
            continue
        if norm(name) in ("TC", "TRANSFER", "AVG", "AVERAGE", "MEAN", "TOTAL"):
            continue
        students.append(row)

    # ---- subject statistics -------------------------------------------------
    subject_rows = {}
    for col, header in graded_cols:
        key = subj_key(header)
        maximum = maxima[key]
        marks, percents = [], []
        for row in students:
            value = numeric(ws.cell(row=row, column=col).value)
            if value is None:
                continue
            marks.append(value)
            percents.append(value / maximum * 100.0)
        canonical = CANON.get(key)
        if canonical is None:
            continue
        stats = {"highest": "", "average": ""}
        if marks:
            top = max(marks)
            stats["highest"] = int(top) if float(top).is_integer() else round(top, 2)
            stats["average"] = round(sum(marks) / len(marks), 2)
        stats.update(band_counts(percents))
        subject_rows[canonical] = stats

    # ---- class level --------------------------------------------------------
    overall = []
    for row in students:
        value = numeric(ws.cell(row=row, column=per_col).value) if per_col else None
        if value is None:
            total = sum(
                v for v in (numeric(ws.cell(row=row, column=c).value) for c, _ in graded_cols)
                if v is not None
            )
            value = total / sum(maxima[subj_key(h)] for _, h in graded_cols) * 100.0

        overall.append(value)

    passed = sum(1 for p in overall if p >= PASS_MARK)
    detained = sum(1 for p in overall if p < PASS_MARK)
    improve = sum(1 for p in overall if PASS_MARK <= p < IMPROVE_MARK)

    return {
        "strength": len(students),
        "class_teacher": class_teacher_from_sheet(ws) or cls_teacher(section),
        "subjects": subject_rows,
        "passed": passed,
        "detained": detained,
        "improve": improve,
        "graded": [h for _, h in graded_cols],
    }


def build_rows(section, exam_type, result):
    base = {
        "exam_name": "%s %s" % (exam_type, SESSION),
        "exam_type": exam_type,
        "class_section": section,
        "exam_period_from": "",
        "exam_period_to": "",
        "class_strength": result["strength"],
        # Filled from the sheet's "C.T." note when present, else from
        # CLASS_TEACHER_OVERRIDE; other hand-written fields (exam period,
        # subject teachers, date) are left blank deliberately.
        "class_teacher_name": result["class_teacher"],
        "subject_teacher": "",
        "no_students_passed": result["passed"],
        "detained": result["detained"],
        "advised_for_improvement": result["improve"],
        "date": "",
    }

    ordered = list(FORMAT_SUBJECTS)
    for subject in result["subjects"]:
        if subject not in ordered:
            ordered.append(subject)

    rows = []
    slots = len(FORMAT_SUBJECTS) + SPARE_ROWS
    for index in range(slots):
        subject = ordered[index] if index < len(ordered) else ""
        row = dict(base)
        row["subject"] = subject
        stats = result["subjects"].get(subject, {})
        if stats:
            row["highest_marks"] = stats["highest"]
            row["average_marks"] = stats["average"]
            for band in BANDS:
                row[band] = stats[band]
        else:
            row["highest_marks"] = ""
            row["average_marks"] = ""
            for band in BANDS:
                row[band] = ""
        rows.append(row)
    return rows


def main():
    written = []
    for section in CLASSES:
        folder = os.path.join(ROOT, section)
        if not os.path.isdir(folder):
            print("!! missing folder: %s" % section)
            continue
        # drop reports we no longer want (e.g. earlier PT runs)
        for stale in os.listdir(folder):
            if stale.startswith("Result Analysis") and stale.endswith(".csv"):
                if not any(stale.upper().find(e) >= 0 for e in WANTED_EXAMS):
                    os.remove(os.path.join(folder, stale))
                    print("   removed %s / %s" % (section, stale))
        books = sorted(
            os.path.join(folder, n) for n in os.listdir(folder)
            if n.lower().endswith(".xlsx") and not n.startswith("~$")
            and not n.startswith("Result Analysis")
        )
        if not books:
            print("!! no workbook in %s" % section)
            continue

        for book in books:
            wb = openpyxl.load_workbook(book, data_only=True)
            used = set()
            for ws in wb.worksheets:
                exam_type = exam_type_for(section, ws.title)
                if exam_type is None:
                    print("   skip sheet (unknown exam): %s / %s" % (section, ws.title))
                    continue
                if exam_type not in WANTED_EXAMS:
                    print("   skip sheet (%s): %s / %s" % (exam_type, section, ws.title))
                    continue
                if (section, exam_type) not in MAXMARKS:
                    raise RuntimeError(
                        "no max-marks config for %s / %s" % (section, exam_type)
                    )
                result = analyse_sheet(ws, section, exam_type)
                rows = build_rows(section, exam_type, result)
                out_name = "Result Analysis - %s %s.csv" % (exam_type, SESSION)
                if out_name in used:
                    out_name = "Result Analysis - %s %s (%s).csv" % (
                        exam_type, SESSION, re.sub(r"\W+", "_", ws.title).strip("_"),
                    )
                used.add(out_name)
                out_path = os.path.join(folder, out_name)
                with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
                    writer = csv.DictWriter(fh, fieldnames=HEADER, quoting=csv.QUOTE_ALL)
                    writer.writeheader()
                    writer.writerows(rows)
                written.append(out_path)
                print(
                    "%-6s %-13s -> %-38s strength=%d passed=%d detained=%d improve=%d subjects=%s"
                    % (section, exam_type, os.path.basename(out_path), result["strength"],
                       result["passed"], result["detained"], result["improve"],
                       ", ".join(result["graded"]))
                )
            wb.close()

    print("\n%d CSV file(s) written." % len(written))
    for path in written:
        print("  " + os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()

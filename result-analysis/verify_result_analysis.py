#!/usr/bin/env python3
"""Independently verify the generated Result Analysis CSVs against the source
workbooks (recomputed with pandas, not the generator's openpyxl path).

Also reports how many students fall into the original PDF's 75%-90% band gap.
"""

import csv
import importlib.util
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location(
    "gen", os.path.join(ROOT, "generate_result_analysis.py")
)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def load_source(section, exam_type):
    folder = os.path.join(ROOT, section)
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".xlsx") or name.startswith("~$"):
            continue
        if name.startswith("Result Analysis"):
            continue
        xl = pd.ExcelFile(os.path.join(folder, name))
        for sheet in xl.sheet_names:
            if gen.exam_type_for(section, sheet) != exam_type:
                continue
            raw = pd.read_excel(os.path.join(folder, name), sheet_name=sheet,
                                header=None, dtype=object)
            hdr = gen.find_header_row(pd_wrapper(raw))
            if hdr is None:
                continue
            df = pd.read_excel(os.path.join(folder, name), sheet_name=sheet,
                               header=hdr - 1, dtype=object)
            df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
            return df
    raise SystemExit("source not found for %s / %s" % (section, exam_type))


class _Cell:
    def __init__(self, value):
        self.value = value


class pd_wrapper:
    def __init__(self, df):
        self.df = df
        self.max_row = len(df)
        self.max_column = len(df.columns)

    def cell(self, row, column):
        return _Cell(self.df.iat[row - 1, column - 1])


def col_index(df, header):
    target = gen.subj_key(header)
    for i, c in enumerate(df.columns):
        if gen.subj_key(c) == target:
            return i
    return None


def is_absent(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def num(v):
    if is_absent(v) or isinstance(v, str):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def recompute(df, section, exam_type):
    maxima = gen.MAXMARKS[(section, exam_type)]
    name_col = next(i for i, c in enumerate(df.columns) if "NAME" in str(c).upper())
    per_col = next((i for i, c in enumerate(df.columns)
                    if re.sub(r"\s+", " ", str(c)).strip().upper() in gen.PER_HEADERS),
                   None)

    mask = []
    for _, row in df.iterrows():
        nm = row.iloc[name_col]
        if is_absent(nm) or str(nm).strip().upper() in ("TC", "TRANSFER"):
            mask.append(False)
        else:
            mask.append(True)
    students = df[mask]

    out = {"strength": len(students), "subjects": {}, "gap": {}}
    for header, maximum in maxima.items():
        ci = col_index(df, header)
        if ci is None:
            continue
        marks, pcts = [], []
        for v in students.iloc[:, ci]:
            x = num(v)
            if x is None:
                continue
            marks.append(x)
            pcts.append(x / maximum * 100.0)
        if not marks:
            continue
        canonical = gen.CANON[gen.subj_key(header)]
        out["subjects"][canonical] = {
            "highest_marks": max(marks),
            "average_marks": round(sum(marks) / len(marks), 2),
            "less_than_40": sum(1 for p in pcts if p < 40),
            "40_to_50": sum(1 for p in pcts if 40 <= p < 50),
            "50_to_60": sum(1 for p in pcts if 50 <= p < 60),
            "60_to_75": sum(1 for p in pcts if 60 <= p < 75),
            "75_to_90": sum(1 for p in pcts if 75 <= p <= 90),
            "more_than_90": sum(1 for p in pcts if p > 90),
        }
        out["gap"][canonical] = sum(1 for p in pcts if 75 <= p <= 90)

    overalls = []
    for _, row in students.iterrows():
        p = num(row.iloc[per_col]) if per_col is not None else None
        if p is None:
            tot = sum(x for x in (num(row.iloc[col_index(df, h)]) for h in maxima) if x)
            p = tot / sum(maxima.values()) * 100.0
        overalls.append(p)
    out["passed"] = sum(1 for p in overalls if p >= 33)
    out["detained"] = sum(1 for p in overalls if p < 33)
    out["improve"] = sum(1 for p in overalls if 33 <= p < 40)
    return out


def main():
    with open(os.path.join(ROOT, "result_analysis_format.csv"), newline="",
              encoding="utf-8-sig") as fh:
        fmt_header = next(csv.reader(fh))

    failures = 0
    checked = 0
    gap_total = 0

    for section in gen.CLASSES:
        folder = os.path.join(ROOT, section)
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".csv") or not name.startswith("Result Analysis"):
                continue
            exam_type = gen.detect_exam_type(name)
            with open(os.path.join(folder, name), newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames != fmt_header:
                    print("HEADER MISMATCH: %s" % name)
                    failures += 1
                    continue
                rows = list(reader)

            df = load_source(section, exam_type)
            expect = recompute(df, section, exam_type)

            got = {r["subject"]: r for r in rows if r["subject"]}
            if int(rows[0]["class_strength"]) != expect["strength"]:
                print("STRENGTH MISMATCH %s: csv=%s src=%s"
                      % (name, rows[0]["class_strength"], expect["strength"]))
                failures += 1
            for label, key in (("no_students_passed", "passed"),
                               ("detained", "detained"),
                               ("advised_for_improvement", "improve")):
                if int(rows[0][label]) != expect[key]:
                    print("COUNT MISMATCH %s %s: csv=%s src=%s"
                          % (name, label, rows[0][label], expect[key]))
                    failures += 1

            for subject, stats in expect["subjects"].items():
                row = got.get(subject)
                if row is None:
                    print("MISSING subject %r in %s" % (subject, name))
                    failures += 1
                    continue
                for field in ("highest_marks", "average_marks", "less_than_40",
                              "40_to_50", "50_to_60", "60_to_75", "75_to_90",
                              "more_than_90"):
                    csv_val = row[field]
                    src_val = stats[field]
                    if isinstance(src_val, float):
                        ok = abs(float(csv_val) - src_val) < 0.005
                    else:
                        ok = int(csv_val) == int(src_val)
                    if not ok:
                        print("MISMATCH %s / %s / %s: csv=%r src=%r"
                              % (name, subject, field, csv_val, src_val))
                        failures += 1
                checked += 1
                gap_total += expect["gap"].get(subject, 0)

            print("%-6s %-38s students=%-3d subjects checked=%-2d  [ok]"
                  % (section, name, expect["strength"], len(expect["subjects"])))

    print("\n%d subject rows verified across all CSVs." % checked)
    print("Students now captured by the added 75-90%% band: %d" % gap_total)
    print("RESULT: %s" % ("ALL CHECKS PASSED" if failures == 0 else "%d FAILURES" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

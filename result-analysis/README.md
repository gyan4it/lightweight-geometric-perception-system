# Result Analysis generator + verifier

Renders the "RESULT ANALYSIS FORMAT" proforma for the seven Half Yearly
2026-27 class reports, from verified CSVs, as print-ready single-page A4
PDFs and editable XLSX.

## Layout

- `generate_result_analysis.py` - builds `data/<class>/Result Analysis -
  HALF-YEARLY 2026-27.csv` from the class master sheets.
- `verify_result_analysis.py` - checks the CSVs (rolls, pass/detain/advise
  rules, bands incl. the added 75%-90% band) before any rendering.
- `render_result_analysis.py` - generates the PDF + XLSX per class. The PDF
  table row height is self-calibrated against the rendered A4 page so the
  report always fills one page without overflow.

## Usage

```
python generate_result_analysis.py      # (re)build the CSVs from masters
python verify_result_analysis.py        # must print RESULT: ALL CHECKS PASSED
python render_result_analysis.py        # writes the PDFs and XLSX
```

Then run the vision-system PDF audit over the outputs, e.g.:

```
python tools/pdf_check.py data/*/...pdf
```

## Ruleset (as specified)

- pass = overall % >= 33 ; advised for improvement = 33 <= % < 40 ;
  detained < 33. Bands: <40, 40-50, 50-60, 60-75, 75-90, >90.
- A.I. is informational only: excluded from overall % and class totals.
- Hand-fill fields (Class Teacher, Period of Examination, Date) are left
  blank for manual completion.
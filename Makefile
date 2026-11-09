PYTHON ?= .venv/bin/python
REPORT_OUT ?= results/paper-local
REPORT_TYPEFACE ?= classic

.PHONY: report report-check

# Rebuild from edited LaTeX and recorded evidence; performs no model inference.
report:
	"$(PYTHON)" scripts/build_paper.py --out "$(REPORT_OUT)" --typeface "$(REPORT_TYPEFACE)"
	"$(PYTHON)" scripts/submission_audit.py --paper-dir "$(REPORT_OUT)"

report-check:
	"$(PYTHON)" scripts/submission_audit.py --paper-dir "$(REPORT_OUT)"

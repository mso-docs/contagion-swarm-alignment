# LaTeX research report

The paper is authored in `paper.tex` and exported to an actual PDF. Author: **Mackenzie O'Brien — Independent AI Researcher, Mac Labs AI**.

The official public DOCX template was inspected: US Letter, one-inch margins,11-point Arial body, Old Standard TT title and recommended section structure. The adaptation and template hash are recorded in `template_format.json`. Main text must be at most8pages, excluding references/appendices; abstract150–250words; limitations/dual-use appendix required. See the [official guidelines](https://apartresearch.com/sprints/swarm-alignment-2026).

Current verified draft: **7main-text pages,11total pages,188abstract words**, before final human review. The paper's compact checkpoint distinguishes any-round deviations from final adoption. It does not silently include new overnight runs.

```bash
.venv/bin/python -m pip install -e '.[analysis]'
.venv/bin/python scripts/build_paper.py
```

The project-local Tectonic compiler is under ignored `.cache/report-tools/tectonic`; another installed compiler can be selected with `--compiler`. The build uses the available Arial system font and downloads the open-licensed title font/TeX resources if missing. It executes the notebook through a private local IPC kernel and never performs model inference. Compiler cache/font metadata and the compiled build manifest remain in ignored local outputs.

Outputs:

- `results/paper-draft/paper.pdf`: compiled research draft.
- `results/paper-draft/paper_figures.executed.ipynb`: executed review notebook with diagrams and explanations.
- `results/paper-draft/figures/`: candidate PDF/SVG/PNG figures, numerical tables and provenance manifest.
- `results/paper-draft/build_manifest.json`: PDF hash, page counts, abstract length and privacy/content checks.

The editable source notebook is `notebooks/paper_figures.ipynb`; frozen numerical evidence is `data/compact_evidence.json`. Figures01,02,07,04 are selected for the main text; topology, reference patching and timing remain appendix diagnostics. Selection emphasizes legibility and scientific interpretation, including null results, rather than effect size.

The separate `notebooks/all_tasks_analysis.ipynb` visualizes all currently indexed live tasks without changing paper claims:

```bash
.venv/bin/python scripts/execute_notebook.py \
  --source notebooks/all_tasks_analysis.ipynb \
  --out results/reports/all-tasks.executed.ipynb
```

Future checkpoints should create a fresh evidence freeze, regenerate candidate figures and revise narrative claims before replacing selected figures. `build_paper.py` rejects data that no longer match the current compact narrative. PDF/source/figures require author review before submission. The implementation PR stays draft and is not automatically merged.

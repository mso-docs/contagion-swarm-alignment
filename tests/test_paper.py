import copy
import json
from pathlib import Path
import runpy

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_paper_distinguishes_intermediate_and_final_endpoints(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    build=runpy.run_path(str(ROOT/'scripts/build_paper.py'))
    data=json.loads((ROOT/'report/data/compact_evidence.json').read_text())
    build['validate_draft_evidence'](data)
    table=build['generated_table'](data)
    assert 'Any-round' in table and 'Final' in table
    assert 'Patch & Injected & 6 & 6 & 0' in table
    changed=copy.deepcopy(data)
    next(r for r in changed['runs'] if r['status']=='completed')['final_any_violation']=True
    with pytest.raises(ValueError,match='transient/final'):build['validate_draft_evidence'](changed)


def test_long_horizon_registry_uses_same_inputs_across_round_budgets(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    queue=runpy.run_path(str(ROOT/'scripts/run_long_horizon.py'))
    # Exercise design construction without accessing a live inference service.
    queue['prepare'].__globals__['validate_readiness']=lambda p:{'readiness_hash':'fixture'}
    from repository_benchmark import sha
    tasks=[{'id':str(i)*20,'input_length':'long','planned_rounds':15,'diff_sha256':str(i)*64} for i in range(3)]
    data={'tasks':tasks};data['catalog_hash']=sha(json.dumps(data,sort_keys=True).encode())
    (tmp_path/'catalog.json').write_text(json.dumps(data))
    initial={'tasks':tasks};initial['freeze_hash']=sha(json.dumps(initial,sort_keys=True).encode())
    (tmp_path/'selection.json').write_text(json.dumps(initial))
    plan=queue['prepare'](tmp_path/'queue',tmp_path/'catalog.json',tmp_path/'selection.json',tmp_path/'proof.json')
    assert plan['planned_runs']==36 and plan['planned_calls']==1560
    freezes=[json.loads((tmp_path/'queue'/f'freeze-h{n:02}.json').read_text()) for n in [3,8,15]]
    assert all([r['id'] for r in f['tasks']]==[r['id'] for r in freezes[0]['tasks']] for f in freezes)
    assert len({f['freeze_hash'] for f in freezes})==3
    assert tasks[0]['id'] not in [r['id'] for r in freezes[0]['tasks']]


def test_temporal_figure_uses_patch_runs_only_not_other_task_denominators(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    analysis=runpy.run_path(str(ROOT/'scripts/paper_analysis.py'))
    data=json.loads((ROOT/'report/data/compact_evidence.json').read_text())
    series=analysis['temporal_patch_series'](data)
    assert sum(values[1]*8 for values in series.values())==17
    assert all(values[0]==0 and values[-1]==0 for values in series.values())


def test_separate_rq3_build_validation_checks_matrix_counts_and_seals(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    build=runpy.run_path(str(ROOT/'scripts/build_paper.py'))
    evidence=json.loads((ROOT/'report/data/rq3_followup.json').read_text())
    narrative=(ROOT/'report/paper.tex').read_text()
    summary=build['validate_rq3_followup'](evidence,narrative)
    assert summary['complete_runs']==64 and summary['responses']==320
    changed=copy.deepcopy(evidence);changed['rows'][1]=copy.deepcopy(changed['rows'][0])
    with pytest.raises(ValueError,match='Duplicate'):build['validate_rq3_followup'](changed,narrative)
    changed=copy.deepcopy(evidence);changed['responses']=325
    with pytest.raises(ValueError,match='header counts'):build['validate_rq3_followup'](changed,narrative)
    changed=copy.deepcopy(evidence);changed['source_seal_sha256'].pop(changed['rows'][0]['run_id'])
    with pytest.raises(ValueError,match='seal coverage'):build['validate_rq3_followup'](changed,narrative)
    changed=copy.deepcopy(evidence);changed['rows'][0]['completed_calls']=4;changed['responses']=319
    with pytest.raises(ValueError,match='five calls'):build['validate_rq3_followup'](changed,narrative)


def test_separate_rq3_build_rejects_false_null_or_stale_narrative(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    validate=runpy.run_path(str(ROOT/'scripts/build_paper.py'))['validate_rq3_followup']
    evidence=json.loads((ROOT/'report/data/rq3_followup.json').read_text())
    narrative=(ROOT/'report/paper.tex').read_text()
    changed=copy.deepcopy(evidence);changed['rows'][0]['attempted_forbidden']=True;changed['attempting_runs']=1
    with pytest.raises(ValueError,match='null narrative'):validate(changed,narrative)
    with pytest.raises(ValueError,match='narrative counts'):validate(evidence,narrative.replace('adds 64 held-out record runs (320 responses)','adds 63 held-out record runs (315 responses)'))
    changed=copy.deepcopy(evidence);changed['rows'][0]['phase']='integration_precheck'
    with pytest.raises(ValueError,match='non-confirmatory'):validate(changed,narrative)


def test_submission_audit_detects_stale_separate_rq3_freeze(tmp_path,monkeypatch):
    import hashlib
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    module=runpy.run_path(str(ROOT/'scripts/submission_audit.py'));audit=module['audit']
    mapping={'latex_source_sha256':'report/paper.tex','bibliography_sha256':'report/sources.bib',
             'analysis_script_sha256':'scripts/paper_analysis.py','notebook_source_sha256':'notebooks/paper_figures.ipynb',
             'rq3_followup_sha256':'report/data/rq3_followup.json','build_script_sha256':'scripts/build_paper.py'}
    from paper_supplement import INPUTS
    mapping.update(INPUTS)
    manifest={}
    for key,name in mapping.items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
        manifest[key]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ['safeguard.json','RQ_ASSESSMENT.md']:
        source=ROOT/'report/data/submission_snapshot'/name
        (tmp_path/'report/data/submission_snapshot'/name).write_bytes(source.read_bytes())
    manifest['rq3_followup_sha256']='0'*64
    paper=tmp_path/'built';paper.mkdir();(paper/'build_manifest.json').write_text(json.dumps(manifest))
    audit.__globals__['ROOT']=tmp_path
    audit.__globals__['inspect_pdf']=lambda *args:{'main_text_pages':7,'total_pages':11,'abstract_words':188}
    result=audit(paper)
    assert result['status']=='stale_build' and result['stale_inputs']==['rq3_followup_sha256']


def test_typeface_variants_change_only_font_declarations(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    build=runpy.run_path(str(ROOT/'scripts/build_paper.py'))
    source=(ROOT/'report/paper.tex').read_text()
    assert build['render_typeface'](source)==source
    compiled=build['render_typeface'](source,'template')
    assert build['TEMPLATE_MAIN'] in compiled and build['TEMPLATE_TITLE'] in compiled
    restored=compiled.replace(build['TEMPLATE_MAIN'],build['CLASSIC_MAIN']).replace(build['TEMPLATE_TITLE'],build['CLASSIC_TITLE'])
    assert restored==source
    assert compiled.split(r'\begin{abstract}',1)[1].split(r'\end{abstract}',1)[0]==source.split(r'\begin{abstract}',1)[1].split(r'\end{abstract}',1)[0]
    with pytest.raises(ValueError,match='Unknown'):build['render_typeface'](source,'invented')
    with pytest.raises(ValueError,match='canonical'):build['render_typeface'](source.replace(build['CLASSIC_TITLE'],''),'template')


def test_pdf_font_names_must_match_declared_variant(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    build=runpy.run_path(str(ROOT/'scripts/build_paper.py'));validate=build['validate_pdf_typeface']
    classic=['/ABCDEF+LMRoman10-Regular','/ABCDEF+LMRoman10-Bold']
    template=['/ABCDEF+ArialMT','/ABCDEF+OldStandardTT-Bold']
    assert validate(classic,'classic')==classic and validate(template,'template')==template
    with pytest.raises(ValueError,match='Embedded'):validate(classic,'template')
    with pytest.raises(ValueError,match='Embedded'):validate(template,'classic')


def test_variant_audit_binds_source_transform_pdf_and_fonts(tmp_path,monkeypatch):
    import hashlib
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    module=runpy.run_path(str(ROOT/'scripts/submission_audit.py'));audit=module['audit']
    mapping={'authoring_source_sha256':'report/paper.tex','bibliography_sha256':'report/sources.bib',
             'analysis_script_sha256':'scripts/paper_analysis.py','notebook_source_sha256':'notebooks/paper_figures.ipynb',
             'rq3_followup_sha256':'report/data/rq3_followup.json','build_script_sha256':'scripts/build_paper.py'}
    from paper_supplement import INPUTS
    mapping.update(INPUTS);manifest={}
    for key,name in mapping.items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/name).read_bytes())
        manifest[key]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ['safeguard.json','RQ_ASSESSMENT.md']:
        (tmp_path/'report/data/submission_snapshot'/name).write_bytes((ROOT/'report/data/submission_snapshot'/name).read_bytes())
    paper=tmp_path/'built';paper.mkdir();source=(tmp_path/'report/paper.tex').read_text()
    compiled=module['render_typeface'](source,'template');(paper/'paper.tex').write_text(compiled);(paper/'paper.pdf').write_bytes(b'actual artifact')
    fonts=['/ABCDEF+ArialMT','/ABCDEF+OldStandardTT-Bold']
    manifest.update(schema_version='paper-build-2.0',typeface_variant='template',pdf_font_names=fonts,
                    compiledlatex_source_sha256=hashlib.sha256(compiled.encode()).hexdigest(),
                    latex_source_sha256=hashlib.sha256(compiled.encode()).hexdigest(),pdf_sha256=hashlib.sha256(b'actual artifact').hexdigest())
    (paper/'build_manifest.json').write_text(json.dumps(manifest));audit.__globals__['ROOT']=tmp_path
    audit.__globals__['inspect_pdf']=lambda *args:{'main_text_pages':7,'total_pages':11,'abstract_words':188}
    audit.__globals__['pdf_font_names']=lambda _:fonts
    result=audit(paper);assert result['stale_inputs']==[] and result['typeface_variant']=='template'
    (paper/'paper.tex').write_text(compiled+'\nChanged science text')
    (paper/'paper.pdf').write_bytes(b'different artifact')
    result=audit(paper)
    assert {'compiled_typeface_transform','compiledlatex_source_sha256','pdf_sha256'}<=set(result['stale_inputs'])

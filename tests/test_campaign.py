import asyncio
import json
from pathlib import Path
import runpy

import pytest

from contagion.studies import StudyPlan

ROOT=Path(__file__).resolve().parents[1]


def api(monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    result=runpy.run_path(str(ROOT/'scripts/run_campaign.py'))
    for name in ['prepare','run']:
        monkeypatch.setitem(result[name].__globals__,'ROOT',tmp_path)
    return result


def plan():
    return StudyPlan(protocol_version='2.6',model='mock-v1',families=['catalog'],max_total_model_calls=50)


def test_campaign_resume_does_not_duplicate_completed_runs(tmp_path,monkeypatch):
    module=api(monkeypatch,tmp_path);root=tmp_path/'campaign'
    frozen=module['prepare'](root,[plan()],'mock')
    first=asyncio.run(module['run'](root));assert first['status']=='completed'
    files=list(Path(frozen['run_root']).rglob('manifest.json'));assert len(files)==2
    again=asyncio.run(module['run'](root));assert again['completed_runs']==2 and again['physical_calls']==0
    assert len(list(Path(frozen['run_root']).rglob('manifest.json')))==2
    assert (root/'monitor/monitor.json').is_file()


def test_stop_flag_prevents_calls_and_can_resume_without_erasing_state(tmp_path,monkeypatch):
    module=api(monkeypatch,tmp_path);root=tmp_path/'campaign'
    frozen=module['prepare'](root,[plan()],'mock');(root/'STOP').write_text('operator pause')
    with pytest.raises(Exception):asyncio.run(module['run'](root))
    assert not list(Path(frozen['run_root']).rglob('events.jsonl'))
    assert json.loads((root/'state.json').read_text())['status']=='stopped'
    (root/'STOP').unlink()
    assert asyncio.run(module['run'](root))['status']=='completed'
    assert 'campaign_stopped' in (root/'journal.jsonl').read_text()


def test_tampered_schedule_and_corrupt_runs_block_resume(tmp_path,monkeypatch):
    module=api(monkeypatch,tmp_path);root=tmp_path/'campaign'
    frozen=module['prepare'](root,[plan()],'mock')
    asyncio.run(module['run'](root))
    path=next(Path(frozen['run_root']).rglob('outcome.json'));path.write_text('{}')
    with pytest.raises(ValueError,match='Corrupt'):asyncio.run(module['run'](root))
    config=json.loads((root/'campaign.json').read_text());config['max_attempts']+=1
    (root/'campaign.json').write_text(json.dumps(config))
    with pytest.raises(ValueError,match='changed'):asyncio.run(module['run'](root))


def test_resource_policy_and_expansion_budget_fail_closed(tmp_path,monkeypatch):
    module=api(monkeypatch,tmp_path)
    assert module['resource_reason']({})
    good={'available_ram_gib':10,'gpu_thermal':[{'temperature_c':50}],'cpu_temperature_c':[45]}
    assert module['resource_reason'](good) is None
    assert module['resource_reason']({**good,'gpu_thermal':[{'temperature_c':90}]})=='gpu_temperature_high'
    with pytest.raises(ValueError):module['prepare'](tmp_path/'large',[plan().model_copy(update={'agent_count':10})],'mock')
    with pytest.raises(ValueError):module['prepare'](tmp_path/'budget',[plan()],'mock',max_attempts=1)


def test_cooling_wait_never_requests_inference_and_requires_stable_cool_samples(tmp_path,monkeypatch):
    module=api(monkeypatch,tmp_path);events=[];sleeps=[];state={}
    samples=iter([{'available_ram_gib':10,'gpu_thermal':[{'temperature_c':55}],'cpu_temperature_c':[92]},
                  {'available_ram_gib':10,'gpu_thermal':[{'temperature_c':55}],'cpu_temperature_c':[78]},
                  {'available_ram_gib':10,'gpu_thermal':[{'temperature_c':55}],'cpu_temperature_c':[77]}])
    async def sleep(seconds):sleeps.append(seconds)
    asyncio.run(module['wait_for_cooling'](lambda:next(samples),lambda **kw:None,
        lambda kind,**kw:events.append(kind),state,lambda:None,sleep))
    assert state['status']=='running' and len(sleeps)==2 and events[-1]=='cooling_complete'


def test_compact_readiness_requires_coverage_and_keeps_budget_interruptions(tmp_path,monkeypatch):
    import shutil
    from contagion.storage import seal
    module=api(monkeypatch,tmp_path)
    from campaign_evidence import compact_evidence
    campaign=module['prepare'](tmp_path/'campaign',[plan()],'mock')
    asyncio.run(module['run'](tmp_path/'campaign'))
    evidence,report=compact_evidence(campaign)
    assert report['completed_conditions']==2 and not report['interrupted_attempts']
    original=next(Path(campaign['run_root']).rglob('manifest.json')).parent
    partial=original.parent/'interrupted-attempt';shutil.copytree(original,partial)
    data=json.loads((partial/'manifest.json').read_text())
    data.update(run_id=partial.name,status='budget_exhausted',failures=['inference_budget'],completed_model_calls=3,
                ended_utc='2020-01-01T00:00:00+00:00')
    (partial/'manifest.json').write_text(json.dumps(data));seal(partial)
    evidence,report=compact_evidence(campaign)
    assert len(report['interrupted_attempts'])==1 and partial/'manifest.json' in evidence
    data['status']='failed';(partial/'manifest.json').write_text(json.dumps(data));seal(partial)
    with pytest.raises(ValueError,match='cannot be waived'):compact_evidence(campaign)


def test_overnight_does_not_start_campaign_after_repository_checkpoint_error(tmp_path,monkeypatch):
    import subprocess
    import sys
    from contagion.config import digest
    from contagion.storage import source_fingerprint
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    module=runpy.run_path(str(ROOT/'scripts/run_overnight.py'))
    frozen={'tasks':[{'id':'case','input_length':'short'}]};frozen['freeze_hash']=digest(frozen)
    freeze=tmp_path/'freeze.json';freeze.write_text(json.dumps(frozen))
    campaign={'provider':'ollama','readiness_hash':'proof','source_hash':source_fingerprint(),'planned_calls':5400}
    (tmp_path/'campaign.json').write_text(json.dumps(campaign))
    monkeypatch.setitem(module['main'].__globals__,'validate_readiness',lambda _: {'readiness_hash':'proof'})
    calls=[]
    def fail(command,**kwargs):
        calls.append(command);raise subprocess.CalledProcessError(1,command)
    monkeypatch.setattr(subprocess,'run',fail)
    monkeypatch.setattr(sys,'argv',['run_overnight','--root',str(tmp_path),'--repository-freeze',str(freeze),
        '--catalog',str(tmp_path/'catalog.json'),'--readiness',str(tmp_path/'proof.json')])
    with pytest.raises(subprocess.CalledProcessError):module['main']()
    state=json.loads((tmp_path/'overnight.json').read_text())
    assert state['status']=='stopped' and state['phase']=='repository-short'
    assert len(calls)==1 and 'scripts/run_campaign.py' not in calls[0]
    with pytest.raises(ValueError,match='fresh supervisor'):module['main']()

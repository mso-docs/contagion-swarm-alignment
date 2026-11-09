"""Offline checks for a reviewed GitHub Pages artifact; never publishes or submits."""
import argparse
from datetime import datetime,timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit

import yaml

from build_dashboard import ASSETS,build
from contagion.publication import validate_snapshot

ROOT=Path(__file__).resolve().parents[1]
VIEWS={'overview','models','evaluations','traces','datasets','research','neural','methods'}
VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=[];self.references=[];self.stack=[];self.selects=[];self.label_for=set();self.nav=set();self.metas={};self.lang=None
    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        if 'id' in data:self.ids.append(data['id'])
        if tag=='html':self.lang=data.get('lang')
        if tag=='meta':self.metas[data.get('http-equiv',data.get('name','')).lower()]=data.get('content','')
        if tag in {'script','img','link','a'}:
            value=data.get('src') if tag in {'script','img'} else data.get('href')
            if value:self.references.append((tag,value))
        if tag=='a' and data.get('id','').startswith('nav-') and data.get('href','').startswith('#'):
            self.nav.add(data['href'][1:])
        if tag=='label' and data.get('for'):self.label_for.add(data['for'])
        if tag=='select':self.selects.append((data.get('id'),bool(data.get('aria-label') or data.get('aria-labelledby') or 'label' in self.stack)))
        if tag not in VOID:self.stack.append(tag)
    def handle_endtag(self,tag):
        if tag in self.stack:self.stack=self.stack[:len(self.stack)-1-self.stack[::-1].index(tag)]


def expected_assets(source):
    """Reconstruct the explicit publication allowlist rather than copying directories."""
    if set(ASSETS)!={'index.html','style.css','app.js','data/results.json'}:raise ValueError('Base publication allowlist requires policy review')
    source=Path(source);assets=set(ASSETS)|{'.nojekyll'}
    if (source/'widgets.js').exists():assets.add('widgets.js')
    for name in ('research','repositories','followups'):
        path=source/f'data/{name}.json'
        if path.exists():assets.add(f'data/{name}.json')
    path=source/'data/research.json'
    if path.exists():
        from contagion.research_publication import validate_research_snapshot
        snapshot=validate_research_snapshot(path)
        if snapshot.suite is not None or snapshot.resources is not None:raise ValueError('Private operational data cannot enter Pages')
        assets.update(row.detail_file for row in snapshot.studies if row.detail_file)
    path=source/'data/trace-samples.json'
    if path.exists():
        from public_trace_samples import validate_index
        samples=validate_index(path)
        assets.add('data/trace-samples.json')
        assets.update(row.file for row in samples.samples)
    return assets


def reference_errors(structure,assets):
    errors=[]
    for tag,value in structure.references:
        url=urlsplit(value)
        if url.scheme or url.netloc:
            if tag=='a' and url.scheme=='https' and not url.username and not url.password:continue
            errors.append('external_or_executable_asset_reference');continue
        if value.startswith('#'):
            if value[1:] not in structure.ids and value[1:] not in VIEWS:errors.append('unknown_internal_anchor')
            continue
        path=unquote(url.path)
        if path.startswith('/') or '\\' in path or '..' in Path(path).parts:
            errors.append('project_prefix_unsafe_reference');continue
        name='index.html' if path in {'','.','./'} else path
        if name not in assets:errors.append('missing_relative_asset')
    return sorted(set(errors))


def workflow_checks(path):
    """Check local workflow policy; branch protection/settings remain operator gates."""
    data=yaml.safe_load(Path(path).read_text())
    jobs=data.get('jobs',{});checks=jobs.get('checks',{});deploy=jobs.get('deploy',{})
    deploy_if=deploy.get('if','');steps=checks.get('steps',[])
    uploads=[s for s in steps if str(s.get('uses','')).startswith('actions/upload-pages-artifact@')]
    def guarded(text):
        condition=re.sub(r'\s+','',text)
        if condition.startswith('${{') and condition.endswith('}}'):condition=condition[3:-2]
        return condition=="github.ref=='refs/heads/main'&&(github.event_name=='push'||github.event_name=='workflow_dispatch')"
    pinned=all(bool(re.fullmatch(r'[^@]+@[a-f0-9]{40}',s['uses'])) for job in jobs.values() for s in job.get('steps',[]) if 'uses' in s)
    return {'main_only_deployment':guarded(deploy_if),'checks_required':deploy.get('needs')=='checks',
            'main_only_artifact_upload':bool(uploads) and all(guarded(s.get('if','')) for s in uploads),
            'job_scoped_pages_permissions':deploy.get('permissions')=={'pages':'write','id-token':'write'} and data.get('permissions')=={'contents':'read'},
            'pinned_actions':pinned,'no_pull_request_target':'pull_request_target' not in data.get('on',data.get(True,{}))}


def inspect(source,artifact,workflow=ROOT/'.github/workflows/pages.yml',now=None):
    source=Path(source).resolve();artifact=Path(artifact).resolve();now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Timezone-aware inspection time required')
    if source==artifact or source in artifact.parents or artifact in source.parents:raise ValueError('Publication source and artifact must be separate')
    expected=expected_assets(source);actual={str(p.relative_to(artifact)) for p in artifact.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=expected:raise ValueError('Artifact differs from the explicit public allowlist')
    if any((artifact/name).is_symlink() or not (artifact/name).is_file() for name in expected):raise ValueError('Unsafe publication asset')
    if (artifact/'.nojekyll').read_bytes():raise ValueError('Unexpected content in generated publication marker')
    if any(sha(artifact/name)!=sha(source/name) for name in expected if name!='.nojekyll'):
        raise ValueError('Publication artifact changed after its validated build')
    from security_guard import private_values
    from serve_dashboard import validate_live_data
    _,values=private_values(ROOT,dict(os.environ));validate_live_data(artifact/'data',values)
    structure=Structure();structure.feed((artifact/'index.html').read_text());app=(artifact/'app.js').read_text()
    errors=reference_errors(structure,expected)
    if errors:raise ValueError('Static references fail: '+','.join(errors))
    if len(structure.ids)!=len(set(structure.ids)):raise ValueError('Duplicate HTML identifiers')
    unlabeled=[ident for ident,wrapped in structure.selects if not wrapped and ident not in structure.label_for]
    if unlabeled:raise ValueError('Unlabeled experiment controls')
    if structure.nav!=VIEWS or structure.lang!='en':raise ValueError('Navigation or language metadata incomplete')
    if "default-src 'self'" not in structure.metas.get('content-security-policy',''):raise ValueError('Missing self-only content policy')
    if 'localAssetRevision' not in app or 'STATIC SNAPSHOT' not in app or 'stale sources:' not in app:
        raise ValueError('Missing local/static distinction or failed-source transparency')
    if 'Mock validation' not in (artifact/'index.html').read_text() or 'LIVE INFERENCE' not in app:
        raise ValueError('Missing live/mock distinction')
    policies=workflow_checks(workflow)
    if not all(policies.values()):raise ValueError('Pages workflow publication policy failed')
    legacy=validate_snapshot(artifact/'data/results.json');indexes=[];warnings=[]
    for name in ('results','research','repositories','followups'):
        path=artifact/f'data/{name}.json'
        if not path.exists():continue
        data=json.loads(path.read_text());generated=data.get('generated_utc');age=None
        if generated:
            stamp=datetime.fromisoformat(generated.replace('Z','+00:00'))
            if stamp.tzinfo is None:raise ValueError('Snapshot timestamp lacks timezone')
            age=max(0,(now-stamp).total_seconds())
        if age is None or age>86400:warnings.append(name+'_snapshot_age_requires_review')
        rows=data.get('runs',data.get('studies',[]))
        indexes.append({'index':name,'generated_utc':generated,'age_seconds':age,'run_attempts':len(rows),
                        'mock_attempts':sum(r.get('backend')=='mock' for r in rows),
                        'live_attempts':sum(r.get('backend') in {'ollama','openai'} for r in rows)})
    return {'schema_version':'publication-readiness-1.0','checked_utc':now.isoformat(),
            'technical_status':'static_artifact_checks_passed','artifact_files':len(actual),
            'inspection_script_sha256':sha(__file__),'build_script_sha256':sha(ROOT/'scripts/build_dashboard.py'),
            'workflow_sha256':sha(workflow),
            'files_sha256':{name:sha(artifact/name) for name in sorted(actual)},'workflow_policy':policies,
            'snapshot_indexes':indexes,'legacy_attempts':len(legacy.runs),'warnings':warnings,
            'deployed':False,'public_access_verified':False,'hackathon_submission_performed':False,
            'manual_gates':['Review code/data revision and optional trace text before publication.',
                            'Confirm repository/Pages visibility and enable Actions publishing if desired.',
                            'Require human review on main through repository branch protection.',
                            'Verify the deployed URL and responsive/browser behavior after authorized deployment.',
                            'Review the exact PDF/template and submit through the organizer form yourself.'],
            'limitations':['Structural accessibility checks are not a complete accessibility or browser-layout audit.',
                           'Snapshot ages describe a fixed reviewed publication, not a live connection to model servers.',
                           'Operational flags and run counts do not establish alignment, collusion, semantic task quality or independent sample size.',
                           'Local privacy validation is heuristic and does not guarantee anonymity.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'dashboard');parser.add_argument('--artifact',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.out.exists():parser.error('Use a fresh readiness output path')
    if args.artifact.resolve() in args.out.resolve().parents:parser.error('Readiness report must remain outside the publication artifact')
    try:
        if args.build:build(args.source,args.artifact)
        result=inspect(args.source,args.artifact)
    except Exception as exc:parser.exit(1,'Publication readiness failed ('+type(exc).__name__+'); inspect private diagnostics without publishing matched text.\n')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('Publication artifact:',result['artifact_files'],'allowlisted files; technical checks passed; deployment/submission not performed.')

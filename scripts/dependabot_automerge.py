"""Merge only bot-authored, green, previously reviewed immutable action updates."""
import json
import os
from pathlib import Path
import re
from http.client import HTTPSConnection

APPROVED={
    'actions/checkout':{'3d3c42e5aac5ba805825da76410c181273ba90b1'},
    'actions/upload-pages-artifact':{'fc324d3547104276b827a68afc52ff2a11cc49c9'},
    'actions/deploy-pages':{'368f82528645a54fb793d4d04e342629a3f51346'},
}
FILES={'.github/workflows/pages.yml','.github/workflows/interpretability.yml'}


def safe_diff(files):
    if not files:return False
    for file in files:
        if file['filename'] not in FILES or file['status']!='modified':return False
        added=[];removed=[]
        for line in file.get('patch','').splitlines():
            if not line.startswith(('+','-')) or line.startswith(('+++','---')):continue
            match=re.fullmatch(r'[+-]\s*- uses: (actions/[a-z-]+)@([a-f0-9]{40})(?:\s*#.*)?',line)
            if not match:return False
            package,pin=match.groups()
            if package not in APPROVED:return False
            if line.startswith('+'):
                if pin not in APPROVED[package]:return False
                added.append(package)
            else:removed.append(package)
        if not added or sorted(added)!=sorted(removed):return False
    return True


def main():
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text());run=event['workflow_run']
    if run['conclusion']!='success':return
    repository=os.environ['GITHUB_REPOSITORY']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('Invalid repository identifier')
    base='/repos/'+repository
    def api(path,method='GET',data=None):
        connection=HTTPSConnection('api.github.com',timeout=30)
        try:
            connection.request(method,base+path,body=json.dumps(data).encode() if data is not None else None,
                headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'Contagion-reviewed-dependency-policy'})
            response=connection.getresponse()
            if response.status>=300:raise RuntimeError('GitHub API HTTP '+str(response.status))
            return json.loads(response.read())
        finally:connection.close()

    for reference in run.get('pull_requests',[]):
        number=reference['number'];pr=api('/pulls/'+str(number))
        if pr['user']['login']!='dependabot[bot]' or pr['state']!='open' or pr['draft'] or pr['base']['ref']!='main':continue
        if pr['head']['repo']['full_name']!=repository or pr['head']['sha']!=run['head_sha']:continue
        files=api('/pulls/'+str(number)+'/files?per_page=100')
        if pr['changed_files']!=len(files) or not safe_diff(files):continue
        checks=api('/commits/'+pr['head']['sha']+'/check-runs')['check_runs']
        if not any(c['name']=='Security and reproducibility gates' and c['conclusion']=='success' for c in checks):continue
        if any(c['status']!='completed' or c['conclusion'] not in {'success','neutral','skipped'} for c in checks):continue
        status=api('/commits/'+pr['head']['sha']+'/status')
        if status['total_count'] and status['state']!='success':continue
        result=api('/pulls/'+str(number)+'/merge','PUT',{'sha':pr['head']['sha'],'merge_method':'squash',
            'commit_title':'build(deps): update reviewed GitHub action pins',
            'commit_message':'Only allowlisted immutable action pins changed. Current-head security and reproducibility checks passed. Application, experiment and permission changes are excluded by policy.'})
        print('Dependabot PR',number,'merged:',bool(result.get('merged')))


if __name__=='__main__':main()

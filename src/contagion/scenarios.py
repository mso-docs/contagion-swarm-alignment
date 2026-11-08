"""384 auditable synthetic scenario variants in a controller-owned SQLite registry."""
import json
from pathlib import Path
import random
import sqlite3

from .config import canonical, digest
from .storage import write_json
from .tasks import TaskCase, make_case

CATEGORIES={'catalog':'instruction_override','provenance':'source_fabrication',
            'patch':'evaluator_field_tampering','record':'protected_state_update'}


def registry_records():
    records=[]
    for split,count in [('development',64),('evaluation',32)]:
        for family,category in CATEGORIES.items():
            for index in range(count):
                case=make_case(family,split,index)
                content={'family':family,'case_id':case.case_id,'split':split,'variant_index':index,
                         'payload':case.payload,'expected':case.expected,'instruction':case.instruction,'challenge':case.challenge}
                records.append({**content,'category':category,'template_version':'2.0',
                                'generation_method':'deterministic_template_variant','content_hash':digest(content)})
    return sorted(records,key=lambda r:r['case_id'])


def build_database(path, catalog_out=None):
    path=Path(path)
    if path.exists():raise ValueError('Scenario database exists; originals are never overwritten')
    path.parent.mkdir(parents=True,exist_ok=True)
    records=registry_records()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE scenarios (scenario_id TEXT PRIMARY KEY, split TEXT NOT NULL, family TEXT NOT NULL, category TEXT NOT NULL, record_json TEXT NOT NULL)')
        db.execute('CREATE INDEX split_family ON scenarios(split, family)')
        db.executemany('INSERT INTO scenarios VALUES (?, ?, ?, ?, ?)',[(r['case_id'],r['split'],r['family'],r['category'],canonical(r)) for r in records])
    if catalog_out:
        public=[{k:r[k] for k in ['case_id','split','family','category','variant_index','template_version','generation_method','content_hash']} for r in records]
        write_json(Path(catalog_out),{'schema_version':'1.0','scenario_count':len(public),'template_family_count':4,
                   'registry_hash':digest(records),'scenarios':public,
                   'limitations':'384 generated variants of four templates; not 384 independently authored attacks or statistically independent tasks.'})
    return {'scenario_count':len(records),'template_family_count':4,'registry_hash':digest(records)}


def load_registry(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Build the scenario database before selecting/freezing trials')
    # Read-only mode prevents a sampling operation from modifying the registry.
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        records=[json.loads(row[0]) for row in db.execute('SELECT record_json FROM scenarios ORDER BY scenario_id')]
    expected=registry_records()
    if records!=expected:raise ValueError('Registry differs from protocol-2 generated cases; version/review custom scenarios separately')
    return records


def sample_scenarios(path, split, families, count, seed, strategy='stratified'):
    records=load_registry(path)
    eligible=[r for r in records if r['split']==split and r['family'] in families]
    if not 1<=count<=len(eligible):raise ValueError('Scenario sample exceeds eligible database population')
    rng=random.Random(seed)
    if strategy=='uniform':selected=rng.sample(eligible,count)
    elif strategy=='stratified':
        buckets={f:[r for r in eligible if r['family']==f] for f in sorted(families)}
        for values in buckets.values():rng.shuffle(values)
        selected=[]
        while len(selected)<count:
            for family in buckets:
                if buckets[family] and len(selected)<count:selected.append(buckets[family].pop())
    else:raise ValueError('Unknown scenario sampling strategy')
    return [TaskCase(r['family'],r['case_id'],r['split'],r['payload'],r['expected']) for r in selected],digest(records)

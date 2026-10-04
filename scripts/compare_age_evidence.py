#!/usr/bin/env python3
"""Rerun age stages on frozen detections, with anonymous review artifacts."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import sys
import threading
import time

ROOT = Path.cwd()


def helper(run=None):
    if run:
        sys.path.insert(0, str(run))
        import full_assignment as h
    else:
        import compare_full_assignment as h
    return h


def prepare(run):
    h = helper()
    old = json.loads((run/'baseline_manifest.json').read_text())
    original = h.rows(run/'source_records.jsonl')
    config = dict(old['crack_config'])
    config.update(L7_MAX_OUTPUT_TOKENS=8192, L8_MAX_OUTPUT_TOKENS=8192)
    shutil.copytree(ROOT/'src/crack', run/'workspace/src/crack', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(run/'baseline_workspace/data', run/'workspace/data')
    for name, source in [('runner.py', Path(__file__)), ('full_assignment.py', ROOT/'scripts/compare_full_assignment.py'),
                         ('protocol.md', ROOT/'experiments/age_evidence/protocol.md'),
                         ('judge_prompt.md', ROOT/'experiments/full_assignment/judge_prompt.md')]:
        shutil.copyfile(source, run/name)
    manifest = {'created_at': h.utc(), 'status': 'prepared', 'model': old['model'], 'concurrency': 4,
                'arm_order': ['baseline', 'age_evidence'], 'crack_config': config,
                'judge_max_completion_tokens': 8192,
                'review_item_ids': [r['item_id'] for r in original if r['analysis']['decision']=='PUN'],
                'frozen_sha256': {name: h.sha(run/name) for name in ['source_records.jsonl','blind.jsonl','gold.jsonl','prechange.json','runner.py','full_assignment.py','protocol.md','judge_prompt.md']},
                'workspace_sha256': h.fingerprints(run)}
    h.write(run/'manifest.json', manifest)
    h.make_packages(run)
    print(run, flush=True)


def infer(run):
    h = helper(run)
    m = h.check_frozen(run)
    h.activate(run)
    from crack.config import Settings
    from crack.schema import AnalysisRecord, LayerTrace
    from crack.runner import execute_layer, _l0_post_layer
    from crack.layers import run_l7, run_l8
    from crack.l2_senses import _aoa_tables
    _aoa_tables()
    settings = Settings(**m['crack_config'])
    original = h.rows(run/'source_records.jsonl')
    packages = {p['item_id']: p for p in h.rows(run/'shared_inputs.jsonl')}
    baseline = []
    for r in original:
        item = dict(r)
        item['api_events'] = []
        item['duration_seconds'] = sum(t['duration_ms'] for t in r['native_record']['trace'] if t['layer'] in {'L7','L8'}) / 1000
        baseline.append(item)
    (run/'baseline').mkdir(exist_ok=False)
    h.jsonl(run/'baseline/records.jsonl', baseline)
    local = threading.local()
    h.observe_sdk(local)
    directory = run/'age_evidence'
    directory.mkdir(exist_ok=False)
    detection_fields = ['l1_result','l2_result','l3_result','l4_result','l5_result','l6_result',
                        'l4_attempts','l4_search','candidate_assessments','candidate_search_version','validation_version']

    def process(old):
        local.events, local.stage = [], None
        rec = AnalysisRecord.model_validate(old['native_record'])
        started = time.monotonic()
        if old['analysis']['decision']=='PUN':
            rec.l7_result = rec.l8_result = None
            rec.final.per_age = {}
            rec.trace = [t for t in rec.trace if t.layer not in {'L7','L8'}]
            for name, fn in [('L7',run_l7),('L8',run_l8)]:
                stage_start = time.monotonic()
                try:
                    rec = execute_layer(name, fn, rec, settings, stage_observer=lambda stage: setattr(local,'stage',stage))
                except Exception as exc:
                    rec.trace.append(LayerTrace(layer=name,status='ERROR',reason=f'{type(exc).__name__}: {exc}',duration_ms=(time.monotonic()-stage_start)*1000))
            rec = _l0_post_layer(rec, settings)
        raw = rec.model_dump(mode='json')
        assert all(raw[k] == old['native_record'].get(k) for k in detection_fields), 'Detection prefix changed'
        assert raw['final']['main_classification']==old['native_record']['final']['main_classification'], 'Detection decision changed'
        assert raw['final']['scope_label']==old['native_record']['final']['scope_label'], 'Scope changed'
        package = packages[old['item_id']]
        common = h.native_view(rec, package)
        h.validate(common, package)
        return {**old, 'native_record': raw,'native_view':common,'analysis':common,'common_contract_passed':True,
                'api_events':local.events,'duration_seconds':time.monotonic()-started,'problems':[],
                'started_at':h.utc(),'finished_at':h.utc()}

    started = time.monotonic()
    print(f"Age stages: {len(m['review_item_ids'])} detector-positive items; 60 fixed detections",flush=True)
    with (directory/'records.jsonl').open('w') as stream, ThreadPoolExecutor(max_workers=m['concurrency']) as pool:
        for count, future in enumerate(as_completed([pool.submit(process,r) for r in original]),1):
            record = future.result()
            stream.write(json.dumps(record,ensure_ascii=False)+'\n'); stream.flush()
            if count%10==0:
                print(f'Progress {count}/60; elapsed {time.monotonic()-started:.1f}s',flush=True)
    h.write(directory/'timing.json',{'batch_wall_seconds':time.monotonic()-started,'age_only':True})
    h.check_frozen(run)
    h.packets(run)
    print('Age inference complete; anonymous packets ready.',flush=True)


def score(run):
    h = helper(run); h.check_frozen(run)
    gold = {g['id']:g for g in h.rows(run/'gold.jsonl')}
    positives = {i for i,g in gold.items() if g['gold_label'] in h.POSITIVE}
    summary = {'run_path':str(run),'scope':'age-only rerun with frozen detection prefix','arms':{}}
    for arm in ['baseline','age_evidence']:
        records = h.rows(run/arm/'records.jsonl'); predictions={r['item_id']:r['analysis'] for r in records}
        if len(records)!=60 or set(predictions)!=set(gold): raise ValueError('Incomplete records')
        metrics = h.detection(predictions,gold)
        metrics['age_gold_positive_labels']=h.age_metrics(predictions,gold,positives)
        metrics['age_all_labels']=h.age_metrics(predictions,gold,set(gold))
        metrics['age_stage_errors']=[{'item_id':r['item_id'],'layer':t['layer'],'reason':t['reason']} for r in records for t in r['native_record']['trace'] if t['layer'] in {'L7','L8'} and t['status']=='ERROR']
        metrics['age_calls_completed']=sum(bool(r['native_record'].get('l7_result')) and bool(r['native_record'].get('l8_result')) for r in records if r['analysis']['decision']=='PUN')
        metrics['api_usage']=h.api_totals(records)
        times=[r['duration_seconds'] for r in records if r['analysis']['decision']=='PUN']
        import statistics
        metrics['mean_age_seconds']=statistics.mean(times)
        metrics['records_sha256']=h.sha(run/arm/'records.jsonl')
        summary['arms'][arm]=metrics
    reviews_path=run/'blind_review/llm_reviews.jsonl'
    if reviews_path.exists():
        from collections import Counter, defaultdict
        keys={k['case']:k for k in json.loads((run/'blind_review/identity_key.json').read_text())}
        reviews=h.rows(reviews_path); percase=defaultdict(list); scores=defaultdict(list); errors=Counter()
        for row in reviews:
            review=row.get('review')
            if not review: continue
            mapping={label:keys[row['case']]['B' if row['swapped'] and label=='A' else 'A' if row['swapped'] and label=='B' else label] for label in ['A','B']}
            preference=review['preference']
            percase[row['case']].append(mapping[preference] if preference!='TIE' else 'TIE')
            for label in ['A','B']:
                for dim,value in review[label]['scores'].items():
                    if value is not None: scores[(mapping[label],dim)].append(value)
                for e in review[label]['errors']: errors[(mapping[label],e['type'])]+=1
        outcome=Counter()
        for case in keys:
            values=percase[case]
            outcome[values[0] if len(values)==2 and len(set(values))==1 else 'ORDER_UNSTABLE' if len(values)==2 else 'INCOMPLETE']+=1
        summary['blind_review']={'requests':len(reviews),'completed':sum(bool(r.get('review')) for r in reviews),'stable_preferences':dict(outcome),
                                'scores':{f'{a}/{d}':{'mean':sum(v)/len(v),'n':len(v)} for (a,d),v in scores.items()},
                                'flagged_errors':{f'{a}/{e}':n for (a,e),n in errors.items()},'api_usage':h.api_totals(reviews),'human_review':'pending','same_model_family':True}
    h.write(run/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['prepare','infer','judge','score']); p.add_argument('--run',required=True,type=Path)
    args=p.parse_args(); run=args.run.resolve()
    if args.action=='prepare': prepare(run)
    elif args.action=='infer': infer(run)
    elif args.action=='judge': helper(run).judge(run)
    else: score(run)

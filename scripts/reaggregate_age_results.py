#!/usr/bin/env python3
"""Revalidate and recombine saved age evidence without any model calls.

Consumes the prepared age_aggregation manifest and envelopes. The source,
input table, evaluator and this script are snapshotted before recomputation.
Gold is read only after all outputs and preservation checks are complete.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def fingerprints(directory):
    return {p.relative_to(directory).as_posix(): sha(p) for p in sorted(directory.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def freeze(run):
    manifest = json.loads((run / 'manifest.json').read_text())
    for name, checksum in {'source_records.jsonl': manifest['source_records_sha256'],
                           **manifest['input_sha256']}.items():
        if sha(run / name) != checksum:
            raise ValueError(f'Frozen input changed: {name}')
    if 'after_source_sha256' not in manifest:
        shutil.copytree(ROOT / 'src/crack', run / 'workspace/src/crack',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (run / 'workspace/data').mkdir(parents=True)
        shutil.copyfile(ROOT / 'data/aoa_kuperman.csv', run / 'workspace/data/aoa_kuperman.csv')
        shutil.copyfile(ROOT / 'scripts/compare_full_assignment.py', run / 'full_assignment.py')
        shutil.copyfile(Path(__file__), run / 'reaggregate_age_results.py')
        manifest['after_source_sha256'] = fingerprints(run / 'workspace')
        manifest['evaluator_sha256'] = sha(run / 'full_assignment.py')
        manifest['runner_sha256'] = sha(run / 'reaggregate_age_results.py')
        # Detection modules and all model instructions must be byte-identical.
        changed = {'src/crack/age_evidence.py', 'src/crack/l7_comprehension.py',
                   'src/crack/l8_appropriateness.py', 'src/crack/schema.py',
                   'src/crack/runner.py', 'src/crack/serve.py', 'src/crack/static/index.html'}
        for name, checksum in manifest['before_source_sha256'].items():
            if name not in changed and sha(run / 'workspace' / name) != checksum:
                raise ValueError(f'Unexpected production change: {name}')
        write(run / 'manifest.json', manifest)
    if fingerprints(run / 'workspace') != manifest['after_source_sha256']:
        raise ValueError('Frozen source or resource changed')
    if sha(run / 'full_assignment.py') != manifest['evaluator_sha256']:
        raise ValueError('Frozen evaluator changed')
    if sha(Path(__file__)) != manifest['runner_sha256']:
        raise ValueError('Runner changed; execute the saved run script instead')
    return manifest


def accepted_reply(record, layer):
    accepted = [a for a in record.age_attempts if a.layer == layer and a.accepted]
    if len(accepted) != 1 or accepted[0].parsed_response is None:
        raise ValueError(f'{record.item_id}: expected one accepted saved {layer} reply')
    reply = accepted[0]
    if not any(json.loads(raw) == reply.parsed_response for raw in reply.raw_responses):
        raise ValueError(f'{record.item_id}: accepted parsed reply differs from raw response')
    return reply.parsed_response


def dimension_metrics(records, gold, ids, dimensions):
    totals = Counter()
    axes = Counter()
    for row in records:
        ident = row['item_id']
        if ident not in ids:
            continue
        l7 = row['native_record'].get('l7_result') or {}
        for age in gold[ident]['expected_age_verdict']:
            totals['total_age_labels'] += 1
            detail = l7.get('per_age_details', {}).get(str(age))
            if not detail:
                totals['without_dimension_assessment'] += 1
                continue
            unknown = [d for d in dimensions if detail[d] == 'UNKNOWN']
            barrier = [d for d in dimensions if detail[d] == 'UNLIKELY']
            totals['ages_with_dimensions'] += 1
            totals['ages_with_unknown_dimensions'] += bool(unknown)
            totals['fully_assessed_ages'] += not unknown
            totals['ages_with_barriers'] += bool(barrier)
            totals['barrier_and_unknown_ages'] += bool(barrier and unknown)
            axes.update(unknown)
    total = totals['total_age_labels']
    return {**dict(totals), 'fully_assessed_coverage': totals['fully_assessed_ages'] / total,
            'unknown_dimensions': dict(axes)}


def run_offline(run):
    manifest = freeze(run)
    sys.path.insert(0, str(run))
    sys.path.insert(0, str(run / 'workspace/src'))
    import full_assignment as h
    from crack import age_evidence
    from crack.enums import ComprehensionStatus
    from crack.l7_comprehension import DIMENSIONS, validate_l7
    from crack.l8_appropriateness import validate_l8
    from crack.schema import AgeVerdict, AnalysisRecord

    def no_model_calls(*args, **kwargs):
        raise RuntimeError('Model calls are forbidden during offline aggregation')

    age_evidence.call_age_model = age_evidence.create_client = no_model_calls
    old_rows = rows(run / 'source_records.jsonl')
    packages = {p['item_id']: p for p in rows(run / 'shared_inputs.jsonl')}
    if len({r['item_id'] for r in old_rows}) != len(old_rows) or set(packages) != {r['item_id'] for r in old_rows}:
        raise ValueError('Duplicate records or input IDs do not match')
    recomputed, changes = [], []
    start = time.monotonic()
    for old in old_rows:
        rec = AnalysisRecord.model_validate(old['native_record'])
        before = rec.model_dump(mode='json')
        package = packages[rec.item_id]
        if rec.text != package['text'] or rec.target_ages != package['target_ages']:
            raise ValueError('Saved text or ages do not match frozen input')
        if rec.l7_result:
            l4 = rec.l4_result
            mandatory = sorted(set(l4.target_term.lower().split()) | {p.lower() for p in l4.split_parts})
            payload = {**package, 'mandatory_vocabulary': mandatory}
            rec.l7_result = validate_l7(accepted_reply(rec, 'L7'), payload)
            if rec.l7_result.aoa_resource_sha256 != before['l7_result']['aoa_resource_sha256']:
                raise ValueError('AoA resource differs from saved evidence')
            if rec.l8_result:
                rec.l8_result = validate_l8(accepted_reply(rec, 'L8'), payload, rec)
            for age, old_verdict in rec.final.per_age.items():
                rec.final.per_age[age] = AgeVerdict(
                    comprehension=rec.l7_result.per_age_comprehension[age],
                    appropriateness=rec.l8_result.per_age_verdict[age] if rec.l8_result else old_verdict.appropriateness)
            rec.age_aggregation_version = age_evidence.AGE_AGGREGATION_VERSION
        after = rec.model_dump(mode='json')
        # Only the derived summaries, version marker and final age labels may differ.
        for key in before.keys() - {'l7_result', 'l8_result', 'final', 'age_aggregation_version'}:
            if before[key] != after[key]:
                raise ValueError(f'{rec.item_id}: preserved field changed: {key}')
        for layer, allowed in [('l7_result', {'per_age_comprehension', 'per_age_summaries', 'aggregation_version'}),
                               ('l8_result', {'per_age_verdict'}), ('final', {'per_age'})]:
            a, b = before.get(layer), after.get(layer)
            if a is None or b is None:
                if a != b:
                    raise ValueError(f'{rec.item_id}: missing stage changed: {layer}')
                continue
            if {k: v for k, v in a.items() if k not in allowed} != {k: v for k, v in b.items() if k not in allowed}:
                raise ValueError(f'{rec.item_id}: underlying evidence changed: {layer}')
        for age, summary in (rec.l7_result.per_age_summaries.items() if rec.l7_result else []):
            detail = rec.l7_result.per_age_details[age]
            if summary.status == ComprehensionStatus.FULLY_COMPREHENSIBLE and any(getattr(detail, d) != 'LIKELY' for d in DIMENSIONS):
                raise ValueError('Non-likely prerequisite was promoted to a pass')
            if summary.unknown_dimensions and not summary.barrier_dimensions and summary.status != ComprehensionStatus.AOA_UNKNOWN:
                raise ValueError('Uncertainty alone was turned into a barrier')
            previous, current = before['final']['per_age'][str(age)], after['final']['per_age'][str(age)]
            if previous != current:
                changes.append({'item_id': rec.item_id, 'age': age, 'before': previous, 'after': current,
                                'summary': summary.model_dump(mode='json')})
        analysis = h.native_view(rec, package)
        h.validate(analysis, package)
        if {k: v for k, v in analysis.items() if k != 'per_age'} != {k: v for k, v in old['analysis'].items() if k != 'per_age'}:
            raise ValueError('Common detection, readings or explanation changed')
        recomputed.append({**old, 'native_record': after, 'native_view': analysis, 'analysis': analysis,
                           'common_contract_passed': True, 'api_events': [],
                           'processing_mode': 'offline_reaggregation', 'new_api_calls': 0,
                           'source_duration_seconds': old['duration_seconds']})
    elapsed = time.monotonic() - start
    destination = run / 'reaggregated'
    destination.mkdir(exist_ok=True)
    h.jsonl(destination / 'records.jsonl', recomputed)
    write(run / 'changes.json', changes)

    # Scoring starts here; gold cannot influence recombination above.
    gold = {g['id']: g for g in rows(run / 'gold.jsonl')}
    if set(gold) != set(packages):
        raise ValueError('Gold IDs differ from the frozen inputs')
    positives = {ident for ident, g in gold.items() if g['gold_label'] in h.POSITIVE}
    arms = {}
    for name, records in [('before', old_rows), ('after', recomputed)]:
        predictions = {r['item_id']: r['analysis'] for r in records}
        arms[name] = {'detection': h.detection(predictions, gold),
                      'gold_pun_age_labels': h.age_metrics(predictions, gold, positives),
                      'all_age_labels': h.age_metrics(predictions, gold, set(gold)),
                      'gold_pun_dimensions': dimension_metrics(records, gold, positives, DIMENSIONS)}
    if arms['before']['detection'] != arms['after']['detection']:
        raise ValueError('Detection metrics changed')
    summary = {'run_path': str(run), 'source_run': manifest['source_run'],
               'scope': 'offline age aggregation; no fresh model or reviewer calls',
               'records': len(recomputed), 'revalidated_l7_l8_pairs': sum(bool(r['native_record'].get('l8_result')) for r in recomputed),
               'new_api_calls': 0, 'new_api_tokens': 0, 'offline_processing_seconds': elapsed,
               'original_inference_times_preserved': True,
               'underlying_evidence_raw_replies_detection_preserved': True,
               'changed_age_verdicts': len(changes), 'changed_comprehension_labels': sum(c['before']['comprehension'] != c['after']['comprehension'] for c in changes),
               'changed_appropriateness_labels': sum(c['before']['appropriateness'] != c['after']['appropriateness'] for c in changes),
               'records_sha256': sha(destination / 'records.jsonl'), 'arms': arms}
    write(run / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    run_offline(parser.parse_args().run.resolve())

"""Independent artifact audit v1.0.0 for the frozen v0.5.8 full benchmark.

Usage: python validate_v058_artifacts_v1.py ORIGINAL_TREE CURATED_TREE EVIDENCE_DIR
This reads results, checkpoints, exact inputs and source. It does not solve models
or edit workflow code/results. It writes one new validation report in EVIDENCE_DIR.
"""
from __future__ import annotations
import ast
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
import math
from pathlib import Path
import re
import subprocess
import sys
VERSION = '1.0.0'
SHA = 'feaabea5d4408d14f15aee47da5399f5d2130be8'
OLD_SHA = '7ee438cf9b1b458d65cba208731520a0e94a4915'
MODE = 'fresh_process_json_condition_isolated'
INPUT_HASHES = {
    'yeast9.0.xml': '0e120b0d4015048ef2edaf86ea039c533a72827ff00a34ca35d9fbe87a2781e5',
    'Yeast9_curated.xml': 'd0bd57f6ec99b8fb1f0ffeb7006ba88a879a9185100236249d6e4bae333a82af',
    'mmc3.xlsx': 'f2cce831331c02b01d734e2867c94063e4d3522ddd018f28314c40830935c9ab',
}
CLASSES = ('correct', 'type_I', 'type_II', 'solver_error', 'input_error')
def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))
def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))
def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
def flag(value: str) -> bool:
    if value not in ('True', 'False'):
        raise ValueError('Invalid boolean field: ' + repr(value))
    return value == 'True'
def independent_class(row: dict[str, str]) -> str:
    if row['missing_genes']:
        return 'input_error'
    if row['ko_status'] != 'optimal' or row['rescue_status'] != 'optimal':
        return 'solver_error'
    ko, rescue, threshold = (float(row[k]) for k in ('ko_growth', 'rescue_growth', 'threshold'))
    if not (math.isfinite(ko) and math.isfinite(rescue)):
        return 'solver_error'
    return 'type_I' if ko >= threshold else 'type_II' if rescue < threshold else 'correct'
def validate(root: Path, label: str, evidence: Path) -> dict:
    result = root / 'results'
    csv_path = result / f'02_{label}_pair_results.csv'
    meta = load(result / f'02_{label}_pair_results.meta.json')
    checkpoint_path = result / f'02_checkpoint_{label}_{MODE}.csv'
    checkpoint = load(result / f'02_checkpoint_{label}_{MODE}.json')
    context = load(evidence / f'context_{label}_v058.json')
    data = rows(csv_path)
    nb_path = root / 'notebooks/02_auxotrophy_reproduction.ipynb'
    nb = load(nb_path)
    constants = {}
    for node in ast.parse(''.join(nb['cells'][1]['source'])).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    sbml = root / 'data/raw' / ('yeast9.0.xml' if label == 'Yeast9' else 'Yeast9_curated.xml')
    model_json = result / 'model_cache' / (label + '.from_sbml.json')
    payload = {
        'workflow_version': '0.5.8', 'workflow_commit': SHA, 'model': label,
        'source_sbml_sha256': digest(sbml), 'model_json_sha256': digest(model_json),
        'dataset_sha256': digest(root / 'data/raw/mmc3.xlsx'),
        'worker_sha256': digest(root / 'scripts/json_pair_worker.py'),
        'python': sys.version, 'cobra': metadata.version('cobra'), 'solver': 'glpk',
        'solver_timeout_seconds': 180, 'process_timeout_seconds': 240,
        'primary_feasibility_tolerance': 1e-7,
        'retry_policy': 'process_timeout_only_tight_feasibility',
        'retry_feasibility_tolerance': 1e-9, 'retry_process_timeout_seconds': 120,
        'threshold': context['run_context']['viability_threshold'],
        'uptake_lower_bound': -1000.0, 'mode': MODE,
    }
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    counts = {name: Counter(r['classification'] for r in data)[name] for name in CLASSES}
    checks = {
        'completed_run_record': context.get('exit_status') == 'completed',
        'input_hashes_match_reference': all(digest(root / 'data/raw' / f) == h for f, h in INPUT_HASHES.items()),
        'source_unchanged_from_execution_commit': not git(root, 'diff', SHA, '--', 'notebooks', 'scripts/json_pair_worker.py'),
        'notebook_runtime_hash_matches': digest(nb_path) == context['notebook_sha256'],
        'workflow_constant_0_5_8': constants['WORKFLOW_VERSION'] == '0.5.8',
        'all_147_pair_ids_once': len(data) == 147 and {r['pair_id'] for r in data} == {f'excel:{n}' for n in range(2, 149)},
        'all_classes_recognized': sum(counts.values()) == len(data),
        'no_solver_error': counts['solver_error'] == 0,
        'no_input_error': counts['input_error'] == 0,
        'metadata_count_and_identity': all(m['completed_pairs'] == 147 and m['workflow_version'] == '0.5.8' and m['workflow_commit'] == SHA and m['model'] == label and m['isolation_mode'] == MODE for m in (meta, checkpoint)),
        'signature_payload_exact': all(m['signature_payload'] == payload for m in (meta, checkpoint)),
        'checkpoint_final_signature_matches_recomputed': all(m['signature'] == signature for m in (meta, checkpoint)),
        'final_csv_sha256_matches': meta['final_csv_sha256'] == digest(csv_path) == context['final_csv_sha256'],
        'checkpoint_and_final_byte_identical': digest(checkpoint_path) == digest(csv_path),
        'classification_recomputed_from_growth_and_status': all(independent_class(r) == r['classification'] for r in data),
        'all_rows_reference_settings': all(r['model'] == label and r['solver'] == 'glpk' and r['condition_isolation'] == 'fresh_model_per_condition' and r['python_executable'] == context['python_executable'] and float(r['threshold']) == payload['threshold'] and float(r['uptake_lower_bound']) == -1000 and float(r['solver_timeout_seconds']) == 180 and float(r['process_timeout_seconds']) == 240 and float(r['primary_feasibility_tolerance']) == 1e-7 and r['model_json_sha256'] == payload['model_json_sha256'] for r in data),
    }
    retry = [r for r in data if flag(r['retry_attempted'])]
    primary = [r for r in data if not flag(r['retry_attempted'])]
    checks['retry_only_after_primary_process_timeout'] = all(flag(r['retry_attempted']) == flag(r['primary_process_timeout']) for r in data)
    checks['retry_policy_and_timeout'] = all(r['retry_policy'] == payload['retry_policy'] and float(r['retry_process_timeout_seconds']) == 120 for r in data)
    checks['primary_provenance_consistent'] = all(r['result_source'] == 'primary' and r['retry_status'] == 'not_attempted' and float(r['feasibility_tolerance']) == 1e-7 and r['retry_feasibility_tolerance'] == '' for r in primary)
    checks['retry_provenance_consistent'] = all(r['result_source'] == 'retry' and r['retry_status'] in ('completed', 'process_timeout') and float(r['feasibility_tolerance']) == 1e-9 and float(r['retry_feasibility_tolerance']) == 1e-9 for r in retry)
    log = (evidence / f'run_{label}_v058.log').read_text(encoding='utf-8')
    durations = {}
    for line in log.splitlines():
        if line.startswith('DONE '):
            match = re.search(r'last=(?:(\d+)h )?(\d+)m (\d+)s', line)
            if match:
                durations[line.split('|')[1].strip()] = sum(int(n or 0) * scale for n, scale in zip(match.groups(), (3600, 60, 1)))
    checks['fresh_full_run_log'] = len(durations) == 147 and 'resuming from' not in log
    checks['retry_elapsed_at_least_primary_timeout'] = all(durations.get(r['pair_id'], 0) >= 240 for r in retry)
    selected = [r for r in data if r['gene_field'] in ('YDL205C', 'YOR278W', 'YPL028W', 'YPL214C')]
    if label == 'Yeast9_curated':
        control = [r for r in selected if r['gene_field'] == 'YPL028W' and r['chemical'] == 'ergosterol']
        checks['r016_control_primary_correct_without_retry'] = len(control) == 1 and control[0]['classification'] == 'correct' and not flag(control[0]['retry_attempted'])
    old_root = root.parent / ('auxoyeast-v057-yeast9' if label == 'Yeast9' else 'auxoyeast-v057-curated')
    old_csv = old_root / 'results' / csv_path.name
    old_meta = load(old_root / 'results' / f'02_{label}_pair_results.meta.json')
    old_signature = hashlib.sha256(json.dumps(old_meta['signature_payload'], sort_keys=True).encode()).hexdigest()
    old_valid = old_meta['workflow_version'] == '0.5.7' and old_meta['workflow_commit'] == OLD_SHA and old_meta['final_csv_sha256'] == digest(old_csv) and old_meta['signature'] == old_signature and old_meta['completed_pairs'] == 147
    old = {r['pair_id']: r for r in rows(old_csv)} if old_valid else {}
    changes = [{'pair_id': r['pair_id'], 'gene': r['gene_field'], 'chemical': r['chemical'], 'v057': old[r['pair_id']]['classification'], 'v058': r['classification']} for r in data if r['pair_id'] in old and r['classification'] != old[r['pair_id']]['classification']]
    fields = ('pair_id', 'gene_field', 'chemical', 'classification', 'ko_status', 'ko_growth', 'rescue_status', 'rescue_growth', 'mapped_rescue', 'primary_process_timeout', 'retry_attempted', 'retry_status', 'feasibility_tolerance', 'result_source')
    reported = 93 if label == 'Yeast9' else 117
    return {
        'model': label, 'checks': checks, 'passed': all(checks.values()),
        'n': len(data), 'counts': counts, 'accuracy_percent': counts['correct'] / len(data) * 100,
        'paper_reference_correct': reported, 'correct_minus_paper': counts['correct'] - reported,
        'benchmark_signature': signature, 'signature_payload': payload,
        'final_csv_sha256': digest(csv_path), 'checkpoint_csv_sha256': digest(checkpoint_path),
        'retry_rows': [{**{k: r[k] for k in fields}, 'elapsed_seconds_floor': durations.get(r['pair_id'])} for r in retry],
        'selected_controls': [{k: r[k] for k in fields} for r in selected],
        'v057_provenance_valid': old_valid, 'classification_changes_vs_v057': changes,
        'execution_record': context,
    }

def main() -> None:
    original, curated, evidence = (Path(p).resolve() for p in sys.argv[1:4])
    report_path = evidence / 'v058_validation_report.json'
    if report_path.exists():
        raise FileExistsError(f'Refusing to overwrite an existing audit: {report_path}')
    models = [validate(original, 'Yeast9', evidence), validate(curated, 'Yeast9_curated', evidence)]
    old_root = original.parent / 'auxoyeast-repro'
    before = load(evidence / 'original_worktree_before.json')
    preserved = git(old_root, 'rev-parse', 'HEAD') == before['head'] and git(old_root, 'status', '--porcelain=v1', '--untracked-files=all') == before['status'] and all(digest(old_root / p) == h for p, h in before['sha256'].items())
    report = {'validator_version': VERSION, 'validator_sha256': digest(Path(__file__)),
              'validated_utc': datetime.now(timezone.utc).isoformat(), 'workflow_commit': SHA,
              'original_dirty_worktree_preserved': preserved, 'models': models,
              'passed': preserved and all(m['passed'] for m in models)}
    with report_path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2); handle.write('\n')
    print(json.dumps({'passed': report['passed'], 'original_dirty_worktree_preserved': preserved,
                      'models': [{k: m[k] for k in ('model', 'n', 'counts', 'passed', 'retry_rows', 'classification_changes_vs_v057')} for m in models]}, indent=2))
    if not report['passed']:
        raise SystemExit(2)

if __name__ == '__main__':
    main()

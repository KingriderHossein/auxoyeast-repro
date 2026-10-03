"""Read-only verification of the persisted v0.5.8 evidence package, v1.0.0.
Usage: python -B scripts/verify_v058_persisted_artifacts_v1.py [--revision INDEX|REF|SHA]
No COBRA model is constructed and no optimization is executed.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import re
import subprocess
from collections import Counter
from pathlib import Path
import openpyxl

VERSION = '1.0.0'
EXECUTION_SHA = 'feaabea5d4408d14f15aee47da5399f5d2130be8'
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default=None)
    args = parser.parse_args()
    checks = {}

    def read(path):
        if args.revision:
            spec = ':' + path if args.revision == 'INDEX' else args.revision + ':' + path
            return subprocess.check_output(['git', '--no-optional-locks', '-C', str(ROOT), 'show', spec])
        return (ROOT / path).read_bytes()

    def load(path):
        return json.loads(read(path).decode('utf-8'))

    def rows(path):
        return list(csv.DictReader(io.StringIO(read(path).decode('utf-8'), newline='')))

    def digest(path):
        return hashlib.sha256(read(path)).hexdigest()

    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise AssertionError(name)

    index = load('results/02_v058_artifact_index.json')
    check('index_execution_identity', index['workflow_commit'] == EXECUTION_SHA)
    check('index_paths_unique', len(index['files']) == len({f['path'] for f in index['files']}))
    for item in index['files']:
        data = read(item['path'])
        check('bytes:' + item['path'], len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'])

    report = load('results/02_v058_validation_report.json')
    check('full_validator_report', report['passed'] and report['original_dirty_worktree_preserved'] and report['workflow_commit'] == EXECUTION_SHA)
    check('validator_source_identity', digest('scripts/validate_v058_artifacts_v1.py') == report['validator_sha256'])
    notes = load('results/02_v058_execution_notes.json')
    check('original_report_byte_copy', notes['report_source_sha256'] == digest('results/02_v058_validation_report.json'))

    book = openpyxl.load_workbook(io.BytesIO(read('data/raw/mmc3.xlsx')), read_only=True, data_only=True)
    values = list(book['all'].iter_rows(values_only=True))
    header = list(values[0])
    dataset = {}
    for number, values_row in enumerate(values[1:], 2):
        raw = dict(zip(header, values_row))
        genes = [s.strip() for s in re.split(r'\s+and\s+', str(raw['Gene Systematic Name']).strip(), flags=re.I) if s.strip()]
        ids = [s.strip() for s in str(raw['ID']).split('+') if s.strip()]
        chemical = str(raw['Chemical']).strip()
        count = len(re.findall(r'\bexchange\b', str(raw['exchange']), flags=re.I))
        conditional = bool(re.search(r'\badd\b', chemical, flags=re.I))
        dataset['excel:' + str(number)] = dict(gene_field=str(raw['Gene Systematic Name']).strip(), chemical=chemical, genes='+'.join(genes), n_genes=len(genes), conditional_medium=str(conditional), rescue=ids[:count] if conditional else ids, background=ids[count:] if conditional else [])
    book.close()
    check('dataset_147_pairs', len(dataset) == 147)
    outputs = {}
    all_counts = {}
    for model, expected_correct, expected_type_I, expected_type_II in [('Yeast9', 92, 37, 18), ('Yeast9_curated', 116, 28, 3)]:
        path = 'results/02_' + model + '_pair_results'
        metadata = load(path + '.meta.json')
        payload = metadata['signature_payload']
        run = next(m for m in report['models'] if m['model'] == model)
        data = rows(path + '.csv')
        outputs[model] = {r['pair_id']: r for r in data}
        counts = Counter(r['classification'] for r in data)
        all_counts[model] = {k: counts[k] for k in ('correct', 'type_I', 'type_II', 'solver_error', 'input_error')}
        check(model + ':pair_identities', len(data) == 147 and len(outputs[model]) == 147 and set(outputs[model]) == set(dataset))
        check(model + ':counts', all_counts[model] == dict(correct=expected_correct, type_I=expected_type_I, type_II=expected_type_II, solver_error=0, input_error=0))
        check(model + ':validator_checks', run['passed'] and all(run['checks'].values()) and run['counts'] == all_counts[model])
        signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        check(model + ':signature', signature == metadata['signature'] == run['benchmark_signature'] and payload == run['signature_payload'])
        check(model + ':metadata', metadata['workflow_version'] == '0.5.8' and metadata['workflow_commit'] == EXECUTION_SHA and metadata['completed_pairs'] == 147 and metadata['isolation_mode'] == 'fresh_process_json_condition_isolated')
        check(model + ':final_sha256', digest(path + '.csv') == metadata['final_csv_sha256'] == run['final_csv_sha256'] == run['checkpoint_csv_sha256'] == run['execution_record']['final_csv_sha256'])
        check(model + ':input_sha256', digest('data/raw/mmc3.xlsx') == payload['dataset_sha256'] and digest('data/raw/' + ('yeast9.0.xml' if model == 'Yeast9' else 'Yeast9_curated.xml')) == payload['source_sbml_sha256'] and digest('scripts/json_pair_worker.py') == payload['worker_sha256'])
        check(model + ':threshold', payload['threshold'] == run['execution_record']['run_context']['viability_threshold'])
        retries = []
        for r in data:
            pair = dataset[r['pair_id']]
            check(model + ':' + r['pair_id'] + ':dataset', all(r[k] == pair[k] for k in ('gene_field', 'chemical', 'genes', 'conditional_medium')) and int(float(r['n_genes'])) == pair['n_genes'])
            # Independently compare actual mapping rows with the validated source rows
            # and Dataset 2 requested IDs. Model-specific missing-ID handling is explicit.
            for part in ('rescue', 'background'):
                mapped = [x for x in r['mapped_' + part].split('+') if x]
                missing = [x for x in r['missing_' + part].split('+') if x]
                requested = list(pair[part])
                translated = ['r_temp1' if model == 'Yeast9_curated' and x == 'a_0001' else x for x in requested]
                check(model + ':' + r['pair_id'] + ':mapping:' + part, Counter(mapped + missing) == Counter(translated))
            ko, rescue, threshold = (float(r[k]) for k in ('ko_growth', 'rescue_growth', 'threshold'))
            classification = 'type_I' if ko >= threshold else 'type_II' if rescue < threshold else 'correct'
            check(model + ':' + r['pair_id'] + ':class', r['ko_status'] == r['rescue_status'] == 'optimal' and not r['missing_genes'] and math.isfinite(ko) and math.isfinite(rescue) and classification == r['classification'] and r['correct'] == str(classification == 'correct'))
            retry = r['retry_attempted'] == 'True'
            check(model + ':' + r['pair_id'] + ':policy', r['model'] == model and r['solver'] == 'glpk' and r['condition_isolation'] == 'fresh_model_per_condition' and float(r['threshold']) == payload['threshold'] and float(r['uptake_lower_bound']) == -1000 and float(r['solver_timeout_seconds']) == 180 and float(r['process_timeout_seconds']) == 240 and float(r['primary_feasibility_tolerance']) == 1e-7 and r['retry_policy'] == 'process_timeout_only_tight_feasibility' and float(r['retry_process_timeout_seconds']) == 120 and r['model_json_sha256'] == payload['model_json_sha256'] and r['python_executable'] == run['execution_record']['python_executable'] and r['primary_process_timeout'] == str(retry))
            if retry:
                retries.append(r['pair_id'])
                check(model + ':' + r['pair_id'] + ':retry', r['result_source'] == 'retry' and r['retry_status'] == 'completed' and float(r['feasibility_tolerance']) == float(r['retry_feasibility_tolerance']) == 1e-9)
            else:
                check(model + ':' + r['pair_id'] + ':primary', r['result_source'] == 'primary' and r['retry_status'] == 'not_attempted' and float(r['feasibility_tolerance']) == 1e-7 and not r['retry_feasibility_tolerance'])
        check(model + ':retry_pairs', retries == ([] if model == 'Yeast9' else ['excel:139', 'excel:140']))

    summary = rows('results/02_benchmark_summary.csv')
    manifest = load('results/02_run_manifest.json')
    check('manifest_identity', manifest['workflow_version'] == '0.5.8' and manifest['workflow_commit'] == EXECUTION_SHA)
    for row in summary:
        check(row['model'] + ':summary', all(int(row[k]) == v for k, v in all_counts[row['model']].items()) and int(row['n']) == 147 and math.isclose(float(row['accuracy']), all_counts[row['model']]['correct'] / 147))
        m = next(r for r in manifest['summary'] if r['model'] == row['model'])
        check(row['model'] + ':manifest_summary', all(m[k] == v for k, v in all_counts[row['model']].items()) and m['n'] == 147)
    comparison = rows('results/02_pairwise_comparison.csv')
    changes = Counter()
    for row in comparison:
        a = outputs['Yeast9'][row['pair_id']]
        b = outputs['Yeast9_curated'][row['pair_id']]
        change = 'fixed' if a['classification'] != 'correct' and b['classification'] == 'correct' else 'regression' if a['classification'] == 'correct' and b['classification'] != 'correct' else 'unchanged'
        check('comparison:' + row['pair_id'], row['classification_original'] == a['classification'] and row['classification_curated'] == b['classification'] and row['change'] == change)
        changes[change] += 1
    check('comparison_totals', len(comparison) == 147 and changes == dict(fixed=26, regression=2, unchanged=119))
    source_nb = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', EXECUTION_SHA + ':notebooks/02_auxotrophy_reproduction.ipynb']).decode('utf-8'))
    executed = load('results/02_v058_executed.ipynb')
    check('notebook_sources_unchanged', len(executed['cells']) == len(source_nb['cells']) and all(a['source'] == b['source'] for a, b in zip(executed['cells'], source_nb['cells'])))
    provenance = executed['metadata']['split_execution_provenance']
    check('assembly_source_identity', provenance['workflow_commit'] == EXECUTION_SHA and digest('scripts/finalize_v058_results_v1.py') == provenance['assembly_script_sha256'])
    check('split_execution_label', 'not one Jupyter-kernel run' in provenance['execution_mode'])
    check('summary_output_present', bool(executed['cells'][8]['outputs']))
    print(json.dumps(dict(verifier_version=VERSION, revision=args.revision or 'working_tree', passed=all(checks.values()), check_count=len(checks), counts=all_counts, comparison_counts=dict(changes), artifact_count=len(index['files'])), indent=2))


if __name__ == '__main__':
    main()

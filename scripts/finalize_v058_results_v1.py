"""Full-run assembly v1.0.0: execute unchanged Notebook 02 cell 8 after audit.

Usage: python finalize_v058_results_v1.py ORIGINAL_TREE CURATED_TREE EVIDENCE_DIR
No optimization or phenotype classification is performed by this harness.
"""
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
VERSION = '1.0.0'
SHA = 'feaabea5d4408d14f15aee47da5399f5d2130be8'
original, curated, evidence = (Path(x).resolve() for x in sys.argv[1:4])
def load(path):
    return json.loads(path.read_text(encoding='utf-8'))
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
report = load(evidence / 'v058_validation_report.json')
assert report['passed'] and report['workflow_commit'] == SHA
assert git(original, 'ls-remote', 'origin', 'refs/heads/main').split()[0] == SHA
for root in (original, curated):
    assert git(root, 'rev-parse', 'HEAD') == SHA
    assert not git(root, 'diff', SHA, '--', 'notebooks', 'scripts/json_pair_worker.py')
    print('PRE_ASSEMBLY_GIT_STATUS', str(root), git(root, 'status', '--porcelain=v1'))
contexts = [load(evidence / ('context_' + label + '_v058.json')) for label in ('Yeast9', 'Yeast9_curated')]
assert contexts[0]['run_context'] == contexts[1]['run_context']
assert all(c['exit_status'] == 'completed' and c['rows'] == 147 for c in contexts)
for root, model in zip((original, curated), report['models']):
    assert digest(root / 'results' / ('02_' + model['model'] + '_pair_results.csv')) == model['final_csv_sha256']
for filename in ('02_run_manifest.json', '02_v058_validation_report.json', '02_v058_executed.ipynb', '02_v058_artifact_index.json'):
    assert not (original / 'results' / filename).exists(), filename
assert not (original / 'results/02_Yeast9_curated_pair_results.meta.json').exists()
assert not git(original, 'diff', '--', 'results/02_Yeast9_curated_pair_results.csv')
for suffix in ('.csv', '.meta.json'):
    src = curated / 'results' / ('02_Yeast9_curated_pair_results' + suffix)
    dst = original / 'results' / src.name
    shutil.copy2(src, dst)
    assert digest(src) == digest(dst)
os.chdir(original)
notebook_path = original / 'notebooks/02_auxotrophy_reproduction.ipynb'
nb = load(notebook_path)
namespace = {'__name__': '__main__', 'display': lambda x: print(x.to_string() if hasattr(x, 'to_string') else x)}
setup_output = io.StringIO()
with contextlib.redirect_stdout(setup_output), contextlib.redirect_stderr(setup_output):
    for index in (1, 2, 3, 4):
        exec(compile(''.join(nb['cells'][index]['source']), str(notebook_path) + ':cell_' + str(index), 'exec'), namespace)
namespace.update(contexts[0]['run_context'])
pd = namespace['pd']
for label, key in (('Yeast9', 'original_results'), ('Yeast9_curated', 'curated_results')):
    namespace[key] = pd.read_csv(original / 'results' / ('02_' + label + '_pair_results.csv'), float_precision='round_trip')
cell8_output = io.StringIO()
with contextlib.redirect_stdout(cell8_output), contextlib.redirect_stderr(cell8_output):
    exec(compile(''.join(nb['cells'][8]['source']), str(notebook_path) + ':cell_8', 'exec'), namespace)
manifest = load(original / 'results/02_run_manifest.json')
assert manifest['workflow_version'] == '0.5.8' and manifest['workflow_commit'] == SHA
for model in report['models']:
    summary_row = next(row for row in manifest['summary'] if row['model'] == model['model'])
    assert summary_row['n'] == model['n']
    assert all(summary_row[key] == value for key, value in model['counts'].items())
    assert digest(original / 'results' / ('02_' + model['model'] + '_pair_results.csv')) == model['final_csv_sha256']
merged_nb = copy.deepcopy(load(evidence / '02_executed_Yeast9_v058.ipynb'))
curated_nb = load(evidence / '02_executed_Yeast9_curated_v058.ipynb')
assert all(a['source'] == b['source'] == c['source'] for a, b, c in zip(nb['cells'], merged_nb['cells'], curated_nb['cells']))
merged_nb['cells'][7] = copy.deepcopy(curated_nb['cells'][7])
merged_nb['cells'][8]['execution_count'] = 8
merged_nb['cells'][8]['outputs'] = [{'output_type': 'stream', 'name': 'stdout', 'text': cell8_output.getvalue().splitlines(True)}]
merged_nb['metadata'].pop('split_execution_provenance', None)
merged_nb['metadata']['split_execution_provenance'] = {
    'assembly_version': VERSION, 'assembled_utc': datetime.now(timezone.utc).isoformat(),
    'workflow_commit': SHA, 'assembly_script_sha256': digest(Path(__file__)),
    'execution_mode': 'Two independent reference-Python processes executed unchanged notebook cells; cell 8 assembled validated CSVs. This is not one Jupyter-kernel run.',
    'cell_sources': {'1-6': contexts[0], '7': contexts[1], '8': 'unchanged source, both validated final CSVs'},
    'markdown_version_note': 'Cell 0 retains the upstream 0.5.5 display heading. Executable WORKFLOW_VERSION and all run signatures are 0.5.8.',
}
with (original / 'results/02_v058_executed.ipynb').open('x', encoding='utf-8', newline='\n') as handle:
    json.dump(merged_nb, handle, indent=1, ensure_ascii=True); handle.write('\n')
shutil.copy2(evidence / 'v058_validation_report.json', original / 'results/02_v058_validation_report.json')
artifacts = [original / 'results' / name for name in (
    '02_Yeast9_pair_results.csv', '02_Yeast9_pair_results.meta.json',
    '02_Yeast9_curated_pair_results.csv', '02_Yeast9_curated_pair_results.meta.json',
    '02_benchmark_summary.csv', '02_pairwise_comparison.csv', '02_run_manifest.json',
    '02_v058_validation_report.json', '02_v058_executed.ipynb')]
index = {'assembly_version': VERSION, 'workflow_commit': SHA,
         'files': [{'path': str(p.relative_to(original)).replace('\\', '/'), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in artifacts]}
with (original / 'results/02_v058_artifact_index.json').open('x', encoding='utf-8', newline='\n') as handle:
    json.dump(index, handle, indent=2); handle.write('\n')
with (evidence / 'cell8_assembly_v058.log').open('x', encoding='utf-8') as handle:
    handle.write(setup_output.getvalue() + cell8_output.getvalue())
print(cell8_output.getvalue())
print('ASSEMBLY_VALIDATED', json.dumps(index, indent=2))

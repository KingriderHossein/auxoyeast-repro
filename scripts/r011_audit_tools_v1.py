"""Read-only R-011 reconciliation helpers, version 1.0.0.

No COBRA import, model construction, or optimization. The notebook owns the
analysis. --verify reads persisted evidence; --execute-notebook runs only the
new analytical notebook's inspected Python cells using this interpreter.
"""
from __future__ import annotations
import argparse
import collections
import contextlib
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import openpyxl

VERSION = "1.0.0"
BASE_SHA = "3ca66b4c119d8968c1ede7769125ef8b3a44fc61"
ROOT = Path(__file__).resolve().parents[1]
OUT = "results/r011/"
MODELS = ("Yeast9", "Yeast9_curated")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(root, path, revision=None):
    if revision:
        spec = ":" + path if revision == "INDEX" else revision + ":" + path
        return subprocess.check_output(["git", "--no-optional-locks", "-C", str(root), "show", spec])
    return (root / path).read_bytes()


def load(root, path, revision=None):
    return json.loads(read(root, path, revision))


def csv_rows(root, path, revision=None):
    return list(csv.DictReader(io.StringIO(read(root, path, revision).decode("utf-8"), newline="")))


def write_json(root, path, value):
    data = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(data)


def write_csv(root, path, rows, fields):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def dataset(root, revision=None):
    book = openpyxl.load_workbook(io.BytesIO(read(root, "data/raw/mmc3.xlsx", revision)), read_only=True, data_only=True)
    values = list(book["all"].iter_rows(values_only=True))
    headers = values[0]
    records = {}
    for number, values_row in enumerate(values[1:], 2):
        raw = dict(zip(headers, values_row))
        genes = tuple(sorted(re.split(r"\s+and\s+", str(raw["Gene Systematic Name"]).strip(), flags=re.I)))
        chemical = str(raw["Chemical"]).strip()
        ids = tuple(x.strip() for x in str(raw["ID"]).split("+") if x.strip())
        count = len(re.findall(r"\bexchange\b", str(raw["exchange"]), flags=re.I))
        conditional = bool(re.search(r"\badd\b", chemical, flags=re.I))
        records["excel:" + str(number)] = dict(pair_id="excel:" + str(number), excel_row=number,
            genes=genes, chemical=chemical, requested_rescue=ids[:count] if conditional else ids,
            requested_background=ids[count:] if conditional else (), conditional=conditional,
            strain=str(raw["Strain Background"]).strip(), experiment_reference=str(raw["Reference"]).strip())
    book.close()
    assert len(records) == 147
    return records


def model_gene_names(root, revision=None):
    ns = "{http://www.sbml.org/sbml/level3/version1/fbc/version2}"
    tree = ET.fromstring(read(root, "data/raw/yeast9.0.xml", revision))
    names = collections.defaultdict(list)
    for element in tree.iter(ns + "geneProduct"):
        names[element.attrib[ns + "label"]].append(element.attrib[ns + "id"])
    return dict(names)


def table1_entries(xml_bytes):
    """Expand HTML rowspans and grouped labels without splitting ALD2 and ALD3."""
    article = ET.fromstring(xml_bytes)
    table = article.find(".//table-wrap[@id='tbl1']/table")
    assert table is not None
    carry = {}
    entries = []
    for number, tr in enumerate(table.findall(".//tr")):
        expanded = {}
        for column, (cell, remaining) in list(carry.items()):
            expanded[column] = cell
            if remaining == 1:
                del carry[column]
            else:
                carry[column] = (cell, remaining - 1)
        column = 0
        own_pair_cell = None
        for cell in tr:
            while column in expanded:
                column += 1
            expanded[column] = cell
            if column == 0:
                own_pair_cell = cell
            rowspan = int(cell.attrib.get("rowspan", "1"))
            if rowspan > 1:
                carry[column] = (cell, rowspan - 1)
            column += int(cell.attrib.get("colspan", "1"))
        if number == 0 or own_pair_cell is None:
            continue
        label = "".join(expanded[1].itertext()).strip()
        segments = []
        current = own_pair_cell.text or ""
        for child in own_pair_cell:
            if child.tag in ("break", "hr"):
                if current.strip():
                    segments.append(current.strip())
                current = child.tail or ""
            else:
                current += "".join(child.itertext()) + (child.tail or "")
        if current.strip():
            segments.append(current.strip())
        for segment in segments:
            gene_field, compound = segment.split("-", 1)
            entries.append(dict(table_row=number, raw_gene_field=gene_field,
                                raw_compound=compound, raw_label=label))
    assert len(entries) == 24
    return entries


def source_class(reference):
    if reference.get("label_semantics") != "paper_auxotrophy_classes":
        return None
    return {"type I": "type_I", "type II": "type_II", "correct": "correct"}.get(reference["raw_label"])


def candidates(pair, references, model):
    """A candidate requires the complete gene set AND complete rescue set.

    Candidate is not a match. Background, label meaning, duplicate record
    identity, reference scope and availability are independent gates below.
    """
    result = []
    for ref in references:
        if ref["model"] != model:
            continue
        gene_sets = ref.get("candidate_gene_sets") or [ref["genes"]]
        if tuple(pair["genes"]) not in [tuple(sorted(g)) for g in gene_sets]:
            continue
        if sorted(pair["requested_rescue"]) != sorted(ref["rescue_ids"]):
            continue
        result.append(ref)
    return result


def compare(pair, references, model, identity_multiplicity=1):
    refs = candidates(pair, references, model)
    relevant = [ref for ref in refs if ref["scope"] == "benchmark"]
    selected = relevant or refs
    if not selected:
        return "not_reported", None, [], "No benchmark-specific prediction found in the inspected package."
    if any(r.get("availability") == "unavailable" for r in selected):
        return "unavailable", None, selected, "Linked reference content is inaccessible."
    if identity_multiplicity != 1 or any(r.get("identity_ambiguous") for r in selected):
        return "ambiguous", None, selected, "Reference cannot select a unique full record or gene-knockout meaning."
    if not relevant:
        return "not_comparable", None, selected, "Systematic positive-prediction graph: benchmark conditions and exact run identity are not supplied."
    if any(r["background_ids"] is None and pair["requested_background"] for r in relevant):
        return "not_comparable", None, selected, "Reference omits the background supplement required by this Dataset 2 record."
    if any(r["background_ids"] is not None and sorted(r["background_ids"]) != sorted(pair["requested_background"]) for r in relevant):
        return "not_comparable", None, selected, "Background supplements differ."
    labels = {source_class(r) for r in relevant}
    if None in labels:
        return "not_comparable", None, selected, "Raw reference label has a different or unspecified meaning."
    if len(labels) != 1:
        return "ambiguous", None, selected, "Conflicting reference classes for the same full identity."
    return "comparable_qualitative", labels.pop(), selected, "Published qualitative benchmark label; exact author run/version/numerical growth remain unavailable."


def reconcile(root, references, revision=None):
    ds = dataset(root, revision)
    counts = collections.Counter((d["genes"], tuple(sorted(d["requested_rescue"])), tuple(sorted(d["requested_background"]))) for d in ds.values())
    records = []
    for model in MODELS:
        source = csv_rows(root, "results/02_" + model + "_pair_results.csv", revision)
        assert len(source) == 147 and len({r["pair_id"] for r in source}) == 147
        assert {r["pair_id"] for r in source} == set(ds)
        for row in source:
            pair = ds[row["pair_id"]]
            assert tuple(sorted(row["genes"].split("+"))) == pair["genes"]
            assert row["chemical"] == pair["chemical"]
            identity = (pair["genes"], tuple(sorted(pair["requested_rescue"])), tuple(sorted(pair["requested_background"])))
            status, ref_class, selected, reason = compare(pair, references, model, counts[identity])
            agreement = ("match" if row["classification"] == ref_class else "mismatch") if status == "comparable_qualitative" else "unknown"
            records.append(dict(model=model, pair_id=row["pair_id"], gene_field=row["gene_field"], genes="+".join(pair["genes"]),
                chemical=pair["chemical"], requested_rescue="+".join(pair["requested_rescue"]),
                requested_background="+".join(pair["requested_background"]), mapped_rescue=row["mapped_rescue"],
                mapped_background=row["mapped_background"], missing_rescue=row["missing_rescue"],
                strain_background=pair["strain"], experimental_reference=pair["experiment_reference"],
                experimental_source_locator="Dataset 2; all!A" + str(pair["excel_row"]) + ":F" + str(pair["excel_row"]),
                current_class=row["classification"], ko_growth=row["ko_growth"], rescue_growth=row["rescue_growth"],
                threshold=row["threshold"], current_model_sha256=load(root, "results/02_" + model + "_pair_results.meta.json", revision)["signature_payload"]["source_sbml_sha256"],
                reference_ids=";".join(r["reference_id"] for r in selected),
                reference_kind=";".join(sorted({r["kind"] for r in selected})) or "no_benchmark_prediction_found",
                raw_reference_value=";".join(r["raw_label"] for r in selected),
                reference_class=ref_class or "", source_ids=";".join(sorted({r["source_id"] for r in selected})) or "ART;SUP;UPSTREAM",
                source_locator=";".join(r["locator"] for r in selected) or "Article sections 2-4; Dataset 1/2 sheets; supplements S1/S2; publication-proximate upstream tree",
                comparability=status, agreement=agreement, exact_run_comparable="False", limitation=reason))
    return records


def summarize(records):
    summary = []
    for model in MODELS:
        rows = [r for r in records if r["model"] == model]
        c = collections.Counter(r["comparability"] for r in rows)
        a = collections.Counter(r["agreement"] for r in rows)
        summary.append(dict(model=model, total=len(rows), comparable_qualitative=c["comparable_qualitative"],
            matches=a["match"], mismatches=a["mismatch"], unknown=a["unknown"],
            not_reported=c["not_reported"], unavailable=c["unavailable"], ambiguous=c["ambiguous"],
            not_comparable=c["not_comparable"], exact_run_comparable=0))
    return summary


def reference_mapping(root, references, revision=None):
    """Separate no-candidate references from candidates superseded by scope."""
    ds = dataset(root, revision)
    mapped = {}
    for ref in references:
        pairs = [d['pair_id'] for d in ds.values() if ref in candidates(d, [ref], ref['model'])]
        mapped[ref['reference_id']] = pairs
    current = reconcile(root, references, revision)
    selected = {rid for row in current for rid in row['reference_ids'].split(';') if rid}
    return dict(
        unmatched_reference_records=[{**r, 'mapping_status':'no_complete_current_identity_candidate'} for r in references if not mapped[r['reference_id']]],
        mapped_not_selected_reference_records=[{**r, 'candidate_pair_ids':mapped[r['reference_id']], 'mapping_status':'benchmark_text_preferred_over_systematic_graph'} for r in references if mapped[r['reference_id']] and r['reference_id'] not in selected],
        multiple_or_ambiguous_current_rows=[dict(model=r['model'],pair_id=r['pair_id'],reference_ids=r['reference_ids'],comparability=r['comparability']) for r in current if ';' in r['reference_ids'] or r['comparability']=='ambiguous'],
        unextracted_visual_scope=['Fig. 4 central crossed MET/TRR1 block','Fig. S2 full graph'],
        note='Unmatched references and unextracted graph edges are not negative author predictions.')


def self_tests():
    p = dict(genes=("A", "B"), requested_rescue=("X",), requested_background=("Y",))
    r = dict(reference_id="test", model="M", genes=["A", "B"], rescue_ids=["X"], background_ids=["Y"],
             scope="benchmark", raw_label="correct", label_semantics="paper_auxotrophy_classes")
    cases = {}
    cases["missing_reference"] = compare(p, [], "M")[0] == "not_reported"
    cases["full_multigene_condition"] = compare(p, [r], "M")[:2] == ("comparable_qualitative", "correct")
    cases["single_gene_not_joint_knockout"] = compare(p, [{**r, "genes": ["A"]}], "M")[0] == "not_reported"
    cases["different_background"] = compare(p, [{**r, "background_ids": ["Z"]}], "M")[0] == "not_comparable"
    cases["unspecified_background"] = compare(p, [{**r, "background_ids": None}], "M")[0] == "not_comparable"
    cases["different_rescue"] = compare(p, [{**r, "rescue_ids": ["Z"]}], "M")[0] == "not_reported"
    cases["ambiguous_duplicate_mapping"] = compare(p, [r], "M", 2)[0] == "ambiguous"
    cases["conflicting_labels"] = compare(p, [r, {**r, "raw_label": "type I"}], "M")[0] == "ambiguous"
    cases["different_label_semantics"] = compare(p, [{**r, "label_semantics": "experimental_auxotrophy"}], "M")[0] == "not_comparable"
    cases["inaccessible_reference"] = compare(p, [{**r, "availability": "unavailable"}], "M")[0] == "unavailable"
    cases["systematic_graph_not_benchmark"] = compare(p, [{**r, "scope": "systematic"}], "M")[0] == "not_comparable"
    assert all(cases.values()), cases
    return cases


def verify(root, revision=None):
    checks = {}
    def check(name, value):
        checks[name] = bool(value)
        assert value, name
    manifest = load(root, OUT + "audit_manifest.json", revision)
    for item in manifest["files"] + manifest["fixed_inputs"]:
        data = read(root, item["path"], revision)
        check("hash:" + item["path"], sha(data) == item["sha256"] and len(data) == item["bytes"])
    refs = load(root, OUT + "reference_records.json", revision)
    registry = load(root, OUT + "source_registry.json", revision)
    source_ids = {r["source_id"] for r in registry["sources"]}
    check("unique_reference_ids", len(refs) == len({r["reference_id"] for r in refs}))
    for ref in refs:
        check("citation:" + ref["reference_id"], ref["source_id"] in source_ids and bool(ref["locator"]) and bool(ref["url"]))
    actual = csv_rows(root, OUT + "pair_crosswalk.csv", revision)
    expected = reconcile(root, refs, revision)
    check("exact_294_keys", len(actual) == 294 and len({(r["model"], r["pair_id"]) for r in actual}) == 294)
    check("crosswalk_recomputed", actual == expected)
    check("summary_recomputed", csv_rows(root, OUT + "coverage_summary.csv", revision) == [{k:str(v) for k,v in r.items()} for r in summarize(expected)])
    check("unknown_never_agreement", all((r["agreement"] == "unknown") == (r["comparability"] != "comparable_qualitative") for r in actual))
    check("reference_mapping_recomputed", load(root, OUT + 'unmatched_and_multiple.json', revision) == reference_mapping(root, refs, revision))
    for row in actual:
        check('row_citation:' + row['model'] + ':' + row['pair_id'], all(s in source_ids for s in row['source_ids'].split(';')) and bool(row['source_locator']) and bool(row['experimental_source_locator']))
    aggregates = csv_rows(root, OUT + 'aggregate_comparison.csv', revision)
    for row in aggregates:
        model_rows = [r for r in actual if r['model'] == row['model']]
        hist = collections.Counter(r['current_class'] for r in model_rows)
        paper = {key:int(row['paper_' + key + ('_text_fig2b' if key == 'correct' else '_fig2b')]) for key in ('correct','type_I','type_II')}
        check('aggregate_denominator:' + row['model'], sum(paper.values()) == int(row['denominator']) == len(model_rows))
        check('aggregate_actual:' + row['model'], all(hist[key] == int(row['current_' + key]) for key in paper))
        check('histogram_bound:' + row['model'], sum(abs(hist[k]-paper[k]) for k in paper)//2 == int(row['conditional_minimum_class_disagreements']))
    for name, result in self_tests().items():
        check("join_test:" + name, result)
    index = load(root, "results/02_v058_artifact_index.json", revision)
    for item in index["files"]:
        check("v058_preserved:" + item["path"], read(root,item["path"],revision) == read(root,item["path"],BASE_SHA))
    check("v058_index_preserved", read(root,"results/02_v058_artifact_index.json",revision) == read(root,"results/02_v058_artifact_index.json",BASE_SHA))
    original_paths = subprocess.check_output(['git','-C',str(root),'ls-tree','-r','--name-only',BASE_SHA,'notebooks'],text=True).splitlines() + ['scripts/json_pair_worker.py', 'scripts/verify_v058_persisted_artifacts_v1.py']
    for path in original_paths:
        data, baseline = read(root,path,revision), read(root,path,BASE_SHA)
        equal = data == baseline
        # Legacy notebooks use Git's existing CRLF checkout conversion. Do not
        # edit them or change their attributes. Exact LF canonical bytes AND a
        # clean path diff establish preservation in this analytical worktree;
        # the four protected source-worktree snapshots check their raw bytes.
        if revision is None and not equal:
            equal = data.replace(b'\r\n',b'\n') == baseline and not subprocess.check_output(['git','-C',str(root),'diff',BASE_SHA,'--',path])
        check('original_source_preserved:' + path, equal)
    nb = load(root, "notebooks/02b_r011_reference_reconciliation.ipynb", revision)
    check("direct_python_label", nb["metadata"]["r011_execution"]["mode"] == "direct Python cell execution; not a Jupyter-kernel run")
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    check("all_analysis_cells_executed", all(c["execution_count"] is not None and c["outputs"] and not any(o["output_type"] == "error" for o in c["outputs"]) for c in code))
    check("notebook_source_hash", sha("\n".join("".join(c["source"]) for c in code).encode()) == manifest["notebook_code_sha256"])
    return dict(version=VERSION, revision=revision or "working_tree", passed=True, check_count=len(checks), reference_records=len(refs), summary=summarize(actual), join_tests=self_tests(), original_source_comparison='Exact Git bytes for revisions; local legacy CRLF notebooks require exact LF canonical bytes plus clean Git diff. Protected source-worktree raw bytes are independently snapshotted.')


def execute_notebook(root):
    import datetime
    path = root / "notebooks/02b_r011_reference_reconciliation.ipynb"
    nb = json.loads(path.read_text(encoding="utf-8"))
    assert not any(c.get("execution_count") is not None for c in nb["cells"] if c["cell_type"] == "code"), "Refuse to overwrite an executed notebook"
    namespace = {"ROOT": root, "__name__": "r011_notebook_execution"}
    before = Path.cwd()
    try:
        os.chdir(root)
        number = 0
        for cell in nb["cells"]:
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell["source"])
            number += 1
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(compile(source, str(path) + "#cell" + str(number), "exec"), namespace)
            cell["execution_count"] = number
            cell["outputs"] = [{"output_type": "stream", "name": "stdout", "text": output.getvalue().splitlines(keepends=True)}]
    finally:
        os.chdir(before)
    nb["metadata"]["r011_execution"] = dict(mode="direct Python cell execution; not a Jupyter-kernel run",
        python_executable=sys.executable, python_version=sys.version, openpyxl_version=openpyxl.__version__,
        executed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), analysis_version=VERSION,
        optimization_executed=False, author_simulation_executed=False)
    # This task-owned notebook is the only existing file updated by this runner.
    path.write_bytes((json.dumps(nb, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps(dict(passed=True, code_cells=number, execution=nb["metadata"]["r011_execution"]), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision")
    parser.add_argument("--execute-notebook", action="store_true")
    args = parser.parse_args()
    if args.execute_notebook:
        assert args.revision is None
        execute_notebook(ROOT)
    else:
        print(json.dumps(verify(ROOT, args.revision), indent=2))

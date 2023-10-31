"""Update Wikidata."""

import json
import webbrowser
from collections import Counter, defaultdict
from pathlib import Path
from textwrap import shorten
from typing import Any, Iterable

import bioontologies
import bioregistry
import click
import pandas as pd
from quickstatements_client import (
    DateQualifier,
    EntityLine,
    QuickStatementsClient,
    TextQualifier,
)
from tabulate import tabulate
from tqdm import tqdm

from build import format_custom_sparql, get_wikidata_records

HERE = Path(__file__).parent.resolve()
PREFIXES_PATH = HERE.joinpath("prefixes.json")
MISSING_WD_ORCIDS_PATH = HERE.joinpath("wikidata_missing_orcids.tsv")
SKIP = {
    "ncbitaxon",
    "gaz",
    "ncit",
    "chebi",
    "omit",
    "pr",
}
WD_URI_PREFIX = "http://www.wikidata.org/entity/"


def secho(*args, **kwargs) -> None:
    tqdm.write(click.style(*args, **kwargs))


@click.command()
@click.option("--dry", is_flag=True)
def main(dry: bool):
    lines: list[EntityLine] = []
    wd_missing_orcids = defaultdict(list)
    resources = [
        resource
        for resource in bioregistry.resources()
        if (
            resource.prefix not in SKIP
            and resource.get_obofoundry_prefix()
            and not resource.is_deprecated()
        )
    ]
    it = tqdm(resources)
    for resource in it:
        it.set_postfix(prefix=resource.prefix)
        try:
            local_missing, local_lines = get_lines(resource.prefix)
        except Exception as e:
            secho(f"{resource.prefix.upper()} failed with {type(e)}: {e}")
            continue
        else:
            for orcid in local_missing:
                wd_missing_orcids[orcid].append(resource.prefix)
            lines.extend(local_lines)

        # do this on every iteration for fast results
        MISSING_WD_ORCIDS_PATH.write_text(
            "".join(
                orcid + "\t" + "|".join(sorted(resources)) + "\n"
                for orcid, resources in sorted(wd_missing_orcids.items())
            )
        )

    if dry:
        secho("Running in dry mode. Quickstatements:", fg="cyan")
        for line in lines:
            secho(str(line))
    else:
        client = QuickStatementsClient()
        res = client.post(lines, batch_name="Add additional ontology contributors")
        webbrowser.open_new_tab(res.batch_url)


def get_existing_orcid_annotation_sparql(ontology_qid: str):
    """Get a SPARQL query that looks for ORCID identifiers that are already annotated to an ontology."""
    return f"SELECT DISTINCT ?orcid WHERE {{ wd:{ontology_qid} wdt:P767/wdt:P496 ?orcid }}"


def get_lines(prefix: str) -> tuple[set[str], list[EntityLine]]:
    pp = bioregistry.get_preferred_prefix(prefix) or prefix
    prefix_to_qid = get_prefix_to_qid()
    ontology_qid = prefix_to_qid.get(prefix)
    if ontology_qid is None:
        secho(f"[{pp}] Could not get QID, skipping", fg="yellow")
        return set(), []

    url = f"http://purl.obolibrary.org/obo/{prefix}.json"
    uri_prefix = f"http://purl.obolibrary.org/obo/{prefix.upper()}_"

    secho(f"[{pp}] getting graph")
    parse_results = bioontologies.get_obograph_by_prefix(prefix)
    if parse_results.graph_document is None:
        secho(f"[{pp}] No graphs, skipping", fg="yellow")
        return set(), []
    data = parse_results.graph_document.dict()

    orcid_counter = count_obograph_orcids(data, uri_prefix=uri_prefix)
    if not orcid_counter:
        secho(
            f"[{pp}] No structured contributor information, skipping",
            fg="yellow",
        )
        return set(), []

    # secho(
    #     tabulate(
    #         orcid_counter.most_common(),
    #         headers=[f"{prefix.upper()} Contributor ORCID", "Count"],
    #         tablefmt="github",
    #     )
    #     + "\n"
    # )

    secho(f"[{pp}] getting existing ORCiD annotations")
    orcids_annotated: set[str] = {
        record["orcid"]
        for record in get_wikidata_records(get_existing_orcid_annotation_sparql(ontology_qid))
    }
    orcids_unannotated = set(orcid_counter) - orcids_annotated
    if not orcids_unannotated:
        secho(
            f"[{pp}] All contributor information is already in Wikidata, skipping",
            fg="yellow",
        )
        return orcids_unannotated, []

    secho(f"[{pp}] getting wikidata records for {len(orcids_unannotated)} ORCiDs")
    records = get_wikidata_records(format_custom_sparql(orcids_unannotated))
    if not records:
        secho(
            f"[{pp}] All {len(orcids_unannotated)} unannotated contributors do not have associated Wikidata records",
            fg="red",
        )
        return orcids_unannotated, []

    for record in records:
        record["count"] = orcid_counter[record["orcid"]]
        record["contributor"] = record["contributor"].removeprefix(WD_URI_PREFIX)
        record["contributorDescription"] = shorten(record["contributorDescription"], 60)

    wd_missing_orcid = orcids_unannotated - {record["orcid"] for record in records}

    df = pd.DataFrame(records)
    secho(f"[{pp}] contributors not already captured by Wikidata:", fg="cyan")
    secho(tabulate(df, headers=list(df.columns), showindex=False) + "\n")

    qualifiers = [
        TextQualifier(predicate="S854", target=url),
        DateQualifier.retrieved("S"),
    ]
    lines = [
        EntityLine(
            subject=ontology_qid,
            predicate="P767",  # contributor
            target=record["contributor"],
            qualifiers=qualifiers,
        )
        for record in records
        if "contributor" in record
    ]
    return wd_missing_orcid, lines


PREFIXES_SPARQL = """\
    SELECT ?prefix ?ontology WHERE {
      ?ontology wdt:P361 wd:Q4117183 ;
                wdt:P1813 ?prefix .
    }
""".rstrip()


def get_prefix_to_qid() -> dict[str, str]:
    if PREFIXES_PATH.is_file():
        return json.loads(PREFIXES_PATH.read_text())
    records = get_wikidata_records(PREFIXES_SPARQL)
    prefix_to_qid = {
        record["prefix"]: record["ontology"].removeprefix(WD_URI_PREFIX) for record in records
    }
    PREFIXES_PATH.write_text(json.dumps(prefix_to_qid, indent=2, sort_keys=True))
    return prefix_to_qid


def count_obograph_orcids(graph_document, *, uri_prefix: str) -> Counter[str]:
    rv: list[str] = []
    for graph in graph_document["graphs"]:
        for node in graph["nodes"]:
            if not node["id"].startswith(uri_prefix):
                continue
            rv.extend(
                orcid.upper() for orcid_raw in iter_orcids(node) if (orcid := orcid_raw.strip())
            )
    return Counter(rv)


def iter_orcids(obj: Any) -> Iterable[str]:
    if isinstance(obj, (list, set)):
        for item in obj:
            yield from iter_orcids(item)
    elif isinstance(obj, dict):
        for item in obj.values():
            yield from iter_orcids(item)
    elif isinstance(obj, str):
        obj = obj.lower().replace(" ", "").replace(",", "").strip()
        if '"' in obj:
            # e.g., in OBI, some are written like 0000-0002-7245-3450"laurenm.wishnie"
            obj = obj[: obj.find('"')]
        if not obj:
            pass
        elif obj.startswith("https://orcid.org/orcid.org/"):
            # see https://github.com/obophenotype/uberon/pull/2845
            yield obj.removeprefix("https://orcid.org/orcid.org/").rstrip("/").strip()
        elif obj.startswith("orcid:orcid.org/"):
            yield obj.removeprefix("orcid:orcid.org/")
        elif obj.startswith("orcid:"):
            yield obj.removeprefix("orcid:").strip()
        elif obj.startswith("http://orcid.org/"):
            yield obj.removeprefix("http://orcid.org/").rstrip("/").strip()
        elif obj.startswith("https://orcid.org/"):
            yield obj.removeprefix("https://orcid.org/").rstrip("/").strip()
        elif obj.startswith("orcid.org/"):
            yield obj.removeprefix("orcid.org/").rstrip("/").strip()
    elif obj is None or isinstance(obj, (bool, float, int)):
        pass
    else:
        tqdm.write(f"unhandled type: {type(obj)}")


if __name__ == "__main__":
    main()

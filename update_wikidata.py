"""Update wikidata."""

import json
import webbrowser
from collections import Counter
from pathlib import Path
from typing import Iterable

import bioregistry
import click
import pandas as pd
import requests
from quickstatements_client import (
    DateQualifier,
    EntityLine,
    QuickStatementsClient,
    TextQualifier,
)
from tabulate import tabulate

from build import format_custom_sparql, get_wikidata_records

HERE = Path(__file__).parent.resolve()
PREFIXES_PATH = HERE.joinpath("prefixes.json")
SKIP = {"ncbitaxon"}


@click.command()
@click.option("--dry", is_flag=True)
def main(dry: bool):
    lines = []
    for resource in bioregistry.resources():
        if (
            resource.prefix in SKIP
            or not resource.get_obofoundry_prefix()
            or not resource.get_download_obograph()
        ):
            continue
        click.secho(resource.prefix.upper(), fg="green", bold=True)
        try:
            lines.extend(get_lines(resource.prefix))
        except Exception as e:
            click.secho(f"{resource.prefix.upper()} failed: {e}")
            continue
    if dry:
        click.secho("Running in dry mode. Quickstatements:", fg="cyan")
        for line in lines:
            click.echo(str(line))
    else:
        client = QuickStatementsClient()
        res = client.post(lines, batch_name="Add additional ontology contributors")
        webbrowser.open_new_tab(res.batch_url)


def get_lines(prefix: str) -> list[EntityLine]:
    prefix_to_qid = get_prefix_to_qid()
    ontology_qid = prefix_to_qid[prefix]

    url = f"http://purl.obolibrary.org/obo/{prefix}.json"
    uri_prefix = f"http://purl.obolibrary.org/obo/{prefix.upper()}_"

    click.echo(f"downloading {prefix}")
    data = requests.get(url).json()
    orcid_counter = count_obograph_orcids(data, uri_prefix=uri_prefix)
    if not orcid_counter:
        click.secho(
            f"No structured contributor information in {prefix.upper()}, skipping", fg="yellow"
        )
        return []

    click.secho(f"{prefix.upper()} contributors", fg="cyan")
    click.echo(
        tabulate(orcid_counter.most_common(), headers=["orcid", "count"], tablefmt="github") + "\n"
    )

    sss = f"SELECT DISTINCT ?orcid WHERE {{ wd:{ontology_qid} wdt:P767/wdt:P496 ?orcid }}"
    orcids_annotated = {record["orcid"] for record in get_wikidata_records(sss)}

    orcids_unannotated = set(orcid_counter) - orcids_annotated
    if not orcid_counter:
        click.secho(
            f"All contributor information in {prefix.upper()} is already in Wikidata, skipping",
            fg="yellow",
        )
        return []
    records = get_wikidata_records(format_custom_sparql(orcids_unannotated))
    df = pd.DataFrame(records)
    df["contributor"] = df["contributor"].map(
        lambda s: s.removeprefix("http://www.wikidata.org/entity/")
    )
    click.secho(f"{prefix.upper()} contributors not already captured by Wikidata", fg="cyan")
    click.echo(tabulate(df, headers=list(df.columns), showindex=False) + "\n")

    # TODO report ORCIDs that couldn't be looked up in wikidata

    qualifiers = [
        TextQualifier(predicate="S854", target=url),
        DateQualifier.retrieved("S"),
    ]
    lines = [
        EntityLine(
            subject=ontology_qid,
            predicate="P767",  # contributor
            target=record["contributor"].removeprefix("http://www.wikidata.org/entity/"),
            qualifiers=qualifiers,
        )
        for record in records
    ]
    return lines


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
        record["prefix"]: record["ontology"].removeprefix("http://www.wikidata.org/entity/")
        for record in records
    }
    PREFIXES_PATH.write_text(json.dumps(prefix_to_qid, indent=2, sort_keys=True))
    return prefix_to_qid


def count_obograph_orcids(x, *, uri_prefix: str):
    rv = []
    for graph in x["graphs"]:
        for node in graph["nodes"]:
            if not node["id"].startswith(uri_prefix):
                continue
            rv.extend(iter_orcids(node))
    return Counter(rv)


def iter_orcids(obj) -> Iterable[str]:
    if isinstance(obj, (list, set)):
        for item in obj:
            yield from iter_orcids(item)
    elif isinstance(obj, dict):
        for item in obj.values():
            yield from iter_orcids(item)
    elif isinstance(obj, str):
        if obj.startswith("https://orcid.org/orcid.org/"):
            # see https://github.com/obophenotype/uberon/pull/2845
            yield obj.removeprefix("https://orcid.org/orcid.org/").rstrip("/")
        elif obj.startswith("http://orcid.org/"):
            yield obj.removeprefix("http://orcid.org/").rstrip("/")
        elif obj.startswith("https://orcid.org/"):
            yield obj.removeprefix("https://orcid.org/").rstrip("/")
        elif obj.startswith("orcid.org/"):
            yield obj.removeprefix("orcid.org/").rstrip("/")
    elif isinstance(obj, (bool, float, int)):
        pass
    else:
        print("unhandled", type(obj))


if __name__ == "__main__":
    main()

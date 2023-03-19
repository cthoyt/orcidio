"""Create a slim OWL of ORCID."""

import datetime
import itertools as itt
import os
import time
from pathlib import Path
from typing import Iterable

import click
import requests
from funowl import (
    Annotation,
    AnnotationAssertion,
    Class,
    ClassAssertion,
    NamedIndividual,
    Ontology,
    OntologyDocument,
)
from rdflib import DCTERMS, OWL, RDFS, Literal, Namespace, URIRef

HERE = Path(__file__).parent.resolve()
OFN_PATH = HERE.joinpath("orcidio.ofn")
ORCIDS_PATH = HERE.joinpath("extra_orcids.txt")
ORCID = Namespace("https://orcid.org/")
URI = "https://w3id.org/orcidio/orcidio.owl"
OBO = Namespace("http://purl.obolibrary.org/obo/")
WIKIDATA = Namespace("http://www.wikidata.org/entity/")

PARENT = "http://purl.obolibrary.org/obo/NCBITaxon_9606"

#: A SPARQL query that gets ORCIDs for all people who have ben annotated to have contributed to an OBO ontology
OBO_SPARQL = """\
    SELECT DISTINCT ?orcid ?contributor ?contributorLabel ?contributorDescription
    WHERE {
      wd:Q4117183 ^wdt:P361/wdt:P767 ?contributor .
      ?contributor wdt:P496 ?orcid .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }
    ORDER BY ?orcid
""".rstrip()

CUSTOM_SPARQL_FMT = """\
    SELECT DISTINCT ?orcid ?contributor ?contributorLabel ?contributorDescription
    WHERE {
        VALUES ?orcid { %s }
        ?contributor wdt:P496 ?orcid .
        SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }
    ORDER BY ?orcid
""".rstrip()


def format_custom_sparql(orcids: Iterable[str]) -> str:
    """Format a custom sparql query for the given ORCIDs."""
    return CUSTOM_SPARQL_FMT % " ".join(f'"{orcid}"' for orcid in orcids)


def get_records():
    """Get records from the OBO-centric ORCIDs and custom ORCID list."""
    custom_orcids = {line.strip() for line in ORCIDS_PATH.read_text().splitlines()}
    custom_sparql = format_custom_sparql(custom_orcids)

    return itt.chain(get_wikidata_records(OBO_SPARQL), get_wikidata_records(custom_sparql))


def get_wikidata_records(sparql) -> list[dict[str, any]]:
    """Query the Wikidata SPARQL endpoint and unpack the records."""
    start_time = time.time()
    click.echo("running sparql:")
    click.secho(sparql, fg="magenta")
    res = requests.get(
        "https://query.wikidata.org/sparql",
        params={"query": sparql, "format": "json"},
        headers={
            "User-Agent": "wikidata-orcid-ontology/1.0",
            "Accept": "application/sparql-results+json",
        },
    )
    res.raise_for_status()
    rv = [
        {key: value["value"] for key, value in record.items()}
        for record in res.json()["results"]["bindings"]
    ]
    elapsed = time.time() - start_time
    click.echo(f"retrieved {len(rv):,} records in {elapsed:.2f} seconds")
    return rv


def main():
    """Query the Wikidata SPARQL endpoint and return JSON."""
    today = datetime.date.today().strftime("%Y-%m-%d")

    ontology_iri = URIRef(URI)
    charlie_iri = ORCID["0000-0003-4423-4370"]
    ontology = Ontology(iri=ontology_iri)
    ontology.annotations.extend(
        (
            Annotation(DCTERMS.title, "ORCID in OWL"),
            Annotation(DCTERMS.creator, charlie_iri),
            Annotation(DCTERMS.license, "https://creativecommons.org/publicdomain/zero/1.0/"),
            Annotation(RDFS.seeAlso, "https://github.com/cthoyt/wikidata-orcid-ontology"),
            Annotation(OWL.versionInfo, today),
        )
    )

    human = OBO["NCBITaxon_9606"]
    ontology.declarations(Class(human))
    ontology.annotations.append(AnnotationAssertion(RDFS.label, human, "Homo sapiens"))

    for record in get_records():
        orcid = ORCID[record["orcid"]]
        name = record["contributorLabel"]
        description = record.get("contributorDescription")
        wikidata = record["contributor"]

        ontology.declarations(NamedIndividual(orcid))
        ontology.annotations.extend(
            [
                AnnotationAssertion(
                    RDFS.label,
                    orcid,
                    Literal(name),
                    [Annotation(DCTERMS.source, wikidata)],
                ),
                ClassAssertion(human, orcid),
            ]
        )
        if description:
            ontology.annotations.append(
                AnnotationAssertion(
                    DCTERMS.description,
                    orcid,
                    description,
                    [Annotation(DCTERMS.source, wikidata)],
                )
            )

    doc = OntologyDocument(
        ontology=ontology,
        orcid=ORCID,
        wikidata=WIKIDATA,
        obo=OBO,
        dcterms=DCTERMS,
        owl=OWL,
    )
    click.echo(f"writing to {OFN_PATH}")
    OFN_PATH.write_text(f"{doc}\n")

    cmd = "robot convert --input orcidio.ofn --output orcidio.owl"
    click.secho(cmd, fg="green")
    os.system(cmd)


if __name__ == "__main__":
    main()

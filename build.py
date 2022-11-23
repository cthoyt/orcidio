"""Create a slim OWL of ORCID."""

import datetime
import os
from pathlib import Path

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
from rdflib import DC, DCTERMS, OWL, RDFS, Literal, Namespace

HERE = Path(__file__).parent.resolve()
OFN_PATH = HERE.joinpath("orcidio.ofn")
ORCID = Namespace("https://orcid.org/")
URI = "https://purl.archive.org/purl/biopragmatics/orcidio.owl"
OBO = Namespace("http://purl.obolibrary.org/obo/")
WIKIDATA = Namespace("http://www.wikidata.org/entity/")

PARENT = "http://purl.obolibrary.org/obo/NCBITaxon_9606"
SPARQL = """\
    SELECT DISTINCT ?orcid ?contributor ?contributorLabel ?contributorDescription
    WHERE {
      wd:Q4117183 ^wdt:P361/wdt:P767 ?contributor .
      ?contributor wdt:P496 ?orcid
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }
    ORDER BY ?orcid
"""


def main():
    """Query the Wikidata SPARQL endpoint and return JSON."""
    today = datetime.date.today().strftime("%Y-%m-%d")

    ontology_iri = OBO["orcid.owl"]
    charlie_iri = ORCID["0000-0003-4423-4370"]
    ontology = Ontology(iri=ontology_iri, version=OBO[f"orcid/releases/{today}/orcid.owl"])
    ontology.annotations.extend(
        (
            Annotation(DC.title, "ORCID in OWL"),
            Annotation(DC.creator, charlie_iri),
            Annotation(DCTERMS.license, "https://creativecommons.org/publicdomain/zero/1.0/"),
            Annotation(RDFS.seeAlso, "https://github.com/cthoyt/wikidata-orcid-ontology"),
            Annotation(OWL.versionInfo, today),
        )
    )

    res = requests.get(
        "https://query.wikidata.org/sparql",
        params={"query": SPARQL, "format": "json"},
        headers={
            "User-Agent": "wikidata-orcid-ontology/1.0",
            "Accept": "application/sparql-results+json",
        },
    )
    res.raise_for_status()

    human = OBO["NCBITaxon_9606"]
    ontology.declarations(Class(human))
    ontology.annotations.append(AnnotationAssertion(RDFS.label, human, "Homo sapiens"))

    for record in res.json()["results"]["bindings"]:
        record = {k: v["value"] for k, v in record.items()}

        orcid = ORCID[record["orcid"]]
        name = record["contributorLabel"]
        description = record.get("contributorDescription")
        wikidata = record["contributor"]

        ontology.declarations(NamedIndividual(orcid))
        ontology.annotations.extend(
            [
                AnnotationAssertion(
                    RDFS.label, orcid, Literal(name), [Annotation(DC.source, wikidata)]
                ),
                ClassAssertion(human, orcid),
            ]
        )
        if description:
            ontology.annotations.append(
                AnnotationAssertion(
                    DC.description, orcid, description, [Annotation(DC.source, wikidata)]
                )
            )

    doc = OntologyDocument(
        ontology=ontology,
        dc=DC,
        orcid=ORCID,
        wikidata=WIKIDATA,
        obo=OBO,
        dcterms=DCTERMS,
        owl=OWL,
    )
    with open(OFN_PATH, "w") as file:
        print(str(doc), file=file)

    os.system("robot convert --input orcidio.ofn --output orcidio.owl")


if __name__ == "__main__":
    main()

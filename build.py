"""Create a slim OWL of ORCID."""

from pathlib import Path

import requests
from funowl import (
    AnnotationAssertion,
    Ontology,
    OntologyDocument,
    AnnotationProperty,
    SubAnnotationPropertyOf,
)
from rdflib import DC, RDFS, Namespace, Literal

HERE = Path(__file__).parent.resolve()
OFN_PATH = HERE.joinpath("orcid.ofn")
ORCID = Namespace("https://orcid.org/")
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
    ontology = Ontology()

    res = requests.get(
        "https://query.wikidata.org/sparql",
        params={"query": SPARQL, "format": "json"},
        headers={
            "User-Agent": "wikidata-orcid-ontology/1.0",
            "Accept": "application/sparql-results+json",
        },
    )
    res.raise_for_status()

    parent_uri = OBO["person-property"]
    ontology.declarations(AnnotationProperty(parent_uri))
    ontology.annotations.append(
        AnnotationAssertion(RDFS.label, parent_uri, "Person as Annotation Property")
    )

    for record in res.json()["results"]["bindings"]:
        orcid = ORCID[record["orcid"]["value"]]
        name = record["contributorLabel"]["value"]
        # TODO add
        # description = record["contributorDescription"]["value"]

        ontology.declarations(AnnotationProperty(orcid))
        ontology.annotations.extend(
            [
                AnnotationAssertion(RDFS.label, orcid, Literal(name)),
                AnnotationAssertion(DC.source, orcid, record["contributor"]["value"]),
                SubAnnotationPropertyOf(orcid, parent_uri),
            ]
        )

    doc = OntologyDocument(
        ontology=ontology, dc=DC, orcid=ORCID, wikidata=WIKIDATA, obo=OBO
    )
    with open(OFN_PATH, "w") as file:
        print(str(doc), file=file)


if __name__ == "__main__":
    main()

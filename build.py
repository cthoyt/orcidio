"""Create a slim OWL of ORCID."""

from pathlib import Path

import requests
from funowl import AnnotationAssertion, NamedIndividual, Ontology, OntologyDocument
from rdflib import RDFS, Namespace

HERE = Path(__file__).parent.resolve()
OFN_PATH = HERE.joinpath("orcid.ofn")
ORCID = Namespace("https://orcid.org/")

PARENT = "http://purl.obolibrary.org/obo/NCBITaxon_9606"
SPARQL = """\
    SELECT DISTINCT ?orcid ?contributorLabel ?contributorDescription
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

    for record in res.json()["results"]["bindings"]:
        orcid = ORCID[record["orcid"]["value"]]
        name = record["contributorLabel"]["value"]
        # TODO add
        # description = record["contributorDescription"]["value"]

        ontology.declarations(NamedIndividual(orcid))
        ontology.annotations.extend(
            [
                AnnotationAssertion(RDFS.label, orcid, name),
            ]
        )

    doc = OntologyDocument(ontology=ontology, orcid=ORCID)
    with open(OFN_PATH, "w") as file:
        print(str(doc), file=file)


if __name__ == "__main__":
    main()

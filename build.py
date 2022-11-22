"""Create a slim OWL of ORCID."""

import datetime
from pathlib import Path

import requests
from funowl import (
    AnnotationAssertion,
    Annotation,
    AnnotationProperty,
    Ontology,
    OntologyDocument,
    SubAnnotationPropertyOf,
)
from rdflib import DC, RDFS, Literal, Namespace, DCTERMS

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

    parent_uri = OBO["person-property"]
    ontology.declarations(AnnotationProperty(parent_uri))
    ontology.annotations.extend(
        (
            AnnotationAssertion(RDFS.label, parent_uri, "Person as Annotation Property"),
            AnnotationAssertion(DC.contributor, parent_uri, charlie_iri),
            AnnotationAssertion(
                DC.description,
                parent_uri,
                "A parent property annotation for ORCID identifiers. This formulation was suggested "
                "by Jim Balhoff to avoid the need to encode ORCID identifiers as named individuals, "
                "which would slow down reasoning.",
            ),
        )
    )

    for record in res.json()["results"]["bindings"]:
        record = {k: v["value"] for k, v in record.items()}

        orcid = ORCID[record["orcid"]]
        name = record["contributorLabel"]
        description = record.get("contributorDescription")
        wikidata = record["contributor"]

        ontology.declarations(AnnotationProperty(orcid))
        ontology.annotations.extend(
            [
                AnnotationAssertion(
                    RDFS.label, orcid, Literal(name), [Annotation(DC.source, wikidata)]
                ),
                SubAnnotationPropertyOf(orcid, parent_uri),
            ]
        )
        if description:
            ontology.annotations.append(
                AnnotationAssertion(
                    DC.description, orcid, description, [Annotation(DC.source, wikidata)]
                )
            )

    doc = OntologyDocument(
        ontology=ontology, dc=DC, orcid=ORCID, wikidata=WIKIDATA, obo=OBO, dcterms=DCTERMS
    )
    with open(OFN_PATH, "w") as file:
        print(str(doc), file=file)


if __name__ == "__main__":
    main()

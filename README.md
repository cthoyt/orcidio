# wikidata-orcid-ontology

Motivated by [Bill Duncan's comments](https://obo-communitygroup.slack.com/archives/C01R2D66249/p1669063375689969)
on annotating ORCID identifiers with labels in ontologies, the goal of this repository is to make an OWL
file that has OBO contributors as named individuals.

Build with:

```shell
python build.py
# Currentls has some issues...
robot convert --input orcid.ofn --output orcid.owl
```
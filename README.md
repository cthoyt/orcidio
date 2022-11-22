# wikidata-orcid-ontology

Motivated by [Bill Duncan's comments](https://obo-communitygroup.slack.com/archives/C01R2D66249/p1669063375689969)
on annotating ORCID identifiers with labels in ontologies, the goal of this repository is to make an OWL
file that has OBO contributors as named individuals.

## Screenshot

In this Protege screenshot, you can see that the named individuals are available:

![](img/screenshot-1.png)

You can see anywhere in Protege you use ORCID URIs, they will get shown with their labels and linked back to the named
individuals.

![](img/screenshot-2.png)

## Build

After installing [`robot`](https://robot.obolibrary.org), you can run the following:

```shell
pip install tox
tox
```

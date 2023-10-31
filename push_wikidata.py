import re
from pathlib import Path

import pandas as pd
from quickstatements_client import lines_to_new_tab
from quickstatements_client.sources.orcid import iter_orcid_lines
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}(\d|X)$")
HERE = Path(__file__).parent.resolve()
MISSING_ORCID_PATH = HERE.joinpath("wikidata_missing_orcids.tsv")


def main():
    df = pd.read_csv(MISSING_ORCID_PATH, sep="\t", header=None, names=["orcid", "places"])
    orcids = sorted({orcid for orcid in df["orcid"] if ORCID_RE.fullmatch(orcid)})
    with logging_redirect_tqdm():
        lines = [line for orcid in tqdm(orcids) for line in iter_orcid_lines(orcid)]
    lines_to_new_tab(lines)


if __name__ == "__main__":
    main()

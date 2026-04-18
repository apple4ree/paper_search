import json

import pytest

from scripts import search_arxiv


@pytest.mark.integration
def test_real_arxiv_search(capsys):
    rc = search_arxiv.main(["--query", "transformer attention", "--top", "3"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    for d in data:
        assert "title" in d and d["source"] == "arxiv"
        assert "authors" in d and isinstance(d["authors"], list)

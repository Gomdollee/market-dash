from market_dash.keywords import tokenize, top_keywords


def test_tokenize_drops_stopwords_short_and_numbers():
    assert tokenize("The Fed cuts rates by 25 bps as stocks rally") == ["fed", "cuts", "rates", "bps", "rally"]


def test_tokenize_strips_possessive():
    assert tokenize("Nvidia's earnings beat") == ["nvidia", "earnings", "beat"]


def test_top_keywords_counts_once_per_headline():
    titles = [
        "Fed Fed Fed holds rates",  # 한 제목 안 중복은 1회
        "Fed signals rate path",
        "Oil jumps on supply fears",
    ]
    result = top_keywords(titles, 5)
    assert result[0] == {"word": "fed", "count": 2}


def test_top_keywords_excludes_single_occurrence_and_breaks_ties_alphabetically():
    titles = ["nvidia tesla", "tesla nvidia", "apple"]
    assert top_keywords(titles, 5) == [{"word": "nvidia", "count": 2}, {"word": "tesla", "count": 2}]


def test_top_keywords_limit():
    titles = ["alpha beta gamma"] * 3
    assert len(top_keywords(titles, 2)) == 2

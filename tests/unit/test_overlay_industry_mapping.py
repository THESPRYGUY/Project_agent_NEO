from neo_build.naics import title_for_naics


def test_known_naics_titles():
    assert (
        title_for_naics("237130")
        == "Power and Communication Line and Related Structures Construction"
    )
    assert (
        title_for_naics("518210")
        == "Computing Infrastructure Providers, Data Processing, Web Hosting, and Related Services"
    )


def test_lineage_fallback_when_code_unknown():
    lineage = [
        "Construction",
        "Power and Communication Line and Related Structures Construction",
    ]
    assert (
        title_for_naics("237100", lineage=lineage)
        == "Power and Communication Line and Related Structures Construction"
    )


def test_none_when_no_lineage_and_unknown():
    assert title_for_naics("000000") is None

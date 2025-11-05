from neo_agent.writer import normalise_pii_flags


def test_normalise_pii_flags_deduplicates_and_standardises():
    result = normalise_pii_flags([" Hash ", "mask", "NONE", "mask"])
    assert result == ["hash", "mask"]


def test_normalise_pii_flags_defaults_to_none_for_empty():
    assert normalise_pii_flags([]) == ["none"]


def test_normalise_pii_flags_unknown_values_become_mask():
    assert normalise_pii_flags(["gdpr", "hash"]) == ["mask", "hash"]

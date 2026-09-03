"""Basic checks for the initial package scaffold."""


def test_package_can_be_imported() -> None:
    import enterprise_ontology_agent

    assert enterprise_ontology_agent.__doc__ is not None

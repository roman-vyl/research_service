from pathlib import Path


def test_program_contains_critical_operating_contract() -> None:
    text = (Path(__file__).parents[1] / "autoresearch/program.md").read_text().lower()
    for phrase in (
        "immutable evaluator",
        "read the domain skill",
        "no scalar leaderboard",
        "hard stop",
        "exactly one meaningful",
        "state.json",
        "journal.jsonl",
        "must not modify any tracked",
        "do not ask for human confirmation",
    ):
        assert phrase in text

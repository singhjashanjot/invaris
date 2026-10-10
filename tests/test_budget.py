import json
from decimal import Decimal

from invaris.budget import PersistentSpendBudget
from invaris.providers import SpendBudget


def test_reservation_published_before_network_and_preserved_if_uncertain():
    commits = []
    budget = PersistentSpendBudget(SpendBudget("1", "1", "1"), commits.append)
    reservation, bound = budget.reserve(100, 100)
    assert commits[-1] == bound == Decimal("0.0002")
    budget.abandon_as_uncertain(reservation)
    assert commits[-1] == bound
    assert budget.pending_estimate_usd == bound


def test_measured_settlement_updates_conservative_reservation():
    commits = []
    budget = PersistentSpendBudget(SpendBudget("1", "1", "2"), commits.append)
    reservation, _ = budget.reserve(1000, 1000)
    budget.settle(reservation, 10, 20)
    assert commits[-1] == Decimal("0.00005")


def test_project_ledger_prevents_silent_budget_reset(tmp_path):
    import pytest

    from invaris.budget import ProjectBudgetedProvider
    directory = tmp_path / "artifacts" / "private"
    directory.mkdir(parents=True)
    (directory / "model-spend.json").write_text(json.dumps({"committed_estimate_usd": "1"}))
    with pytest.raises(ValueError, match="exhausted"):
        ProjectBudgetedProvider(tmp_path, "configured-model", 1)

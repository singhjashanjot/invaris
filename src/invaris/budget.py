from __future__ import annotations

import atexit
import json
import threading
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from filelock import FileLock

from .providers import OpenAICompatibleProvider, SpendBudget
from .state import save_checkpoint


class PersistentSpendBudget(SpendBudget):
    def __init__(self, original: SpendBudget, publish: Callable[[Decimal], None]) -> None:
        super().__init__(original.limit, original.input_rate, original.output_rate)
        self.publish = publish
        self.guard = threading.RLock()

    def _publish(self) -> None:
        self.publish(self.spent_estimate_usd + self.pending_estimate_usd)

    def reserve(self, input_token_bound: int, max_output_tokens: int):
        with self.guard:
            result = super().reserve(input_token_bound, max_output_tokens)
            self._publish()
            return result

    def settle(self, reservation_id: int, input_tokens: int | None, output_tokens: int | None):
        with self.guard:
            result = super().settle(reservation_id, input_tokens, output_tokens)
            self._publish()
            return result

    def abandon_as_uncertain(self, reservation_id: int):
        with self.guard:
            result = super().abandon_as_uncertain(reservation_id)
            self._publish()
            return result


class ProjectBudgetedProvider:
    def __init__(self, root: Path, model: str | None, total_limit_usd: float, **provider_options: Any) -> None:
        self.directory = root.resolve() / "artifacts" / "private"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "model-spend.json"
        self.lock = FileLock(str(self.directory / "model-spend.lock"))
        self.lock.acquire(timeout=0)
        atexit.register(self.close)
        try:
            state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            self.previous = Decimal(str(state.get("committed_estimate_usd", "0")))
            self.total_limit = Decimal(str(total_limit_usd))
            if not self.previous.is_finite() or self.previous < 0 or not self.total_limit.is_finite() or self.total_limit <= self.previous:
                raise ValueError("Authorized project estimate cap is exhausted or invalid; no live call allowed")
            self.provider = OpenAICompatibleProvider(model=model, spend_limit_usd=str(self.total_limit - self.previous), **provider_options)
            if self.provider.cost_budget is None:
                raise ValueError("Explicit model rates are required before live calls")
            self.provider.cost_budget = PersistentSpendBudget(self.provider.cost_budget, self._publish)
            self.model = self.provider.model
            self._publish(Decimal(0))
        except BaseException:
            self.close()
            raise

    def _publish(self, current: Decimal) -> None:
        payload = {"committed_estimate_usd": str(self.previous + current), "authorized_total_usd": str(self.total_limit),
                   "billing_guarantee": False, "note": "Settled estimates plus retained worst-case reservations; not invoices. Do not reset to silently extend authorization."}
        save_checkpoint(self.path, payload)

    def next(self, messages, tools):
        return self.provider.next(messages, tools)

    def close(self) -> None:
        if hasattr(self, "lock") and self.lock.is_locked:
            self.lock.release()

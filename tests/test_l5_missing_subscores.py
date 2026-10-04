"""Missing scores are execution failures, with one call and no zero defaults."""
import json
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

import pytest

from crack.config import DEFAULT_SETTINGS
from crack.l5_resolution import resolve_l5
from crack.validation import ModelResponseError
from tests.test_l5 import _qa_record_for_routing


@pytest.mark.parametrize("backend", ["gemini", "anthropic", "openai"])
@pytest.mark.parametrize("missing_field", list(DEFAULT_SETTINGS.L5_QA_WEIGHTS))
def test_missing_subscore_fails_without_retry_or_invented_zero(backend, missing_field):
    payload = {k: .8 for k in DEFAULT_SETTINGS.L5_QA_WEIGHTS if k != missing_field}
    payload.update(evidence_sufficient=True, context_consistent=True, reasoning="A complete assessment was attempted.")
    raw = json.dumps(payload)
    response = NS(text=raw, candidates=[NS(finish_reason="STOP")], stop_reason="end_turn",
                  content=[NS(text=raw)], choices=[NS(finish_reason="stop", message=NS(content=raw, refusal=None))])
    client = MagicMock()
    client.models.generate_content.return_value = response
    client.messages.create.return_value = response
    client.chat.completions.create.return_value = response
    with pytest.raises(ModelResponseError):
        resolve_l5(_qa_record_for_routing(), DEFAULT_SETTINGS.model_copy(update={"L5_BACKEND": backend}),
                   ambiguous_term="guts", client=client)
    assert sum(call.call_count for call in (client.models.generate_content,
               client.messages.create, client.chat.completions.create)) == 1

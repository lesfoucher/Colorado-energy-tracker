"""Tests for the AI summary check. No API calls: Claude is replaced with a fake that returns fixed text."""
import json
from types import SimpleNamespace

import pytest

from pipeline import summarize

DATA = {
    "latest_period": "2026-07",
    "prior_period": "2025-07",
    "headline": {
        "renewable_share_pct": 45.9, "renewable_share_change_pp": 6.6,
        "total_gwh": 5701.9, "total_change_pct": 2.5,
        "coal_gwh": 862.9, "coal_change_pct": -35.6,
        "res_price": 17.0, "res_price_change_pct": 6.3,
    },
}
FACTS = summarize.build_facts(DATA)

GOOD = ("Renewables supplied 45.9% of Colorado's electricity in July 2026, up 6.6 percentage points from "
        "July 2025. Coal generation fell 35.6% to 863 GWh. The average residential price rose 6.3% to 17.0 cents per kWh.")


def test_facts_are_formatted_for_reading():
    levels = {f["label"].split(" in ")[0]: f["value"] for f in FACTS["levels"]}
    assert levels["Total generation"] == "5,702"
    assert levels["Coal generation"] == "863"
    coal = next(c for c in FACTS["changes_vs_prior_year"] if c["label"] == "Coal generation")
    assert (coal["value"], coal["direction"]) == ("35.6", "down")


def test_correct_summary_passes():
    assert summarize.check_summary(GOOD, FACTS) == []


def test_comma_and_no_comma_both_match():
    assert summarize.check_summary("Total generation was 5,702 GWh in July 2026.", FACTS) == []


def test_wrong_number_is_caught():
    problems = summarize.check_summary(GOOD.replace("35.6%", "36.5%"), FACTS)
    assert any("36.5" in p for p in problems)


def test_made_up_number_is_caught():
    problems = summarize.check_summary(GOOD + " Wind supplied 27% of generation.", FACTS)
    assert any("'27'" in p for p in problems)


def test_wrong_direction_is_caught():
    problems = summarize.check_summary("Coal generation rose 35.6% compared with July 2025.", FACTS)
    assert any("Coal generation changed down" in p for p in problems)


def test_unrelated_year_is_caught():
    problems = summarize.check_summary("Renewables reached 45.9%, the highest since 2019.", FACTS)
    assert any("2019" in p for p in problems)


def test_empty_summary_is_rejected():
    assert summarize.check_summary("  ", FACTS) == ["The summary is empty"]


# ---- End to end with a fake Claude client ----

class FakeClient:
    def __init__(self, text=None, refuse=False):
        reply = SimpleNamespace(
            stop_reason="refusal" if refuse else "end_turn",
            content=[] if refuse else [SimpleNamespace(type="text", text=text)],
        )
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: reply))


@pytest.fixture
def summary_path(tmp_path, monkeypatch):
    path = tmp_path / "summary.json"
    monkeypatch.setattr(summarize, "SUMMARY_JSON", path)
    return path


def test_good_summary_is_published(summary_path):
    assert summarize.generate(DATA, FakeClient(GOOD)) == []
    saved = json.loads(summary_path.read_text())
    assert saved["period"] == "2026-07" and saved["text"] == GOOD


def test_bad_summary_is_not_published_and_old_one_is_removed(summary_path):
    summary_path.write_text('{"period": "2026-06", "text": "last month"}')
    problems = summarize.generate(DATA, FakeClient(GOOD.replace("45.9%", "49.5%")))
    assert problems
    assert not summary_path.exists()


def test_refusal_publishes_nothing(summary_path):
    assert summarize.generate(DATA, FakeClient(refuse=True)) == ["Claude declined to write a summary"]
    assert not summary_path.exists()

"""Write a short plain-English summary of the latest month with Claude, then check it.

Every number in the summary must match a number the database produced, and every change must be
described in the right direction. If the check fails, no summary is published that month.

    python -m pipeline.summarize
"""
import json
import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv

from pipeline import export, load

SUMMARY_JSON = load.ROOT / "site" / "summary.json"
MODEL = "claude-opus-5-5"

# A comma only counts as part of a number when it separates thousands ("5,702"), not in "July 2026, up".
NUMBER = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\d,]\d)")
UP_WORDS = {"rose", "risen", "increase", "increased", "increasing", "up", "higher", "grew", "growth", "climbed", "gain", "gained", "jumped"}
DOWN_WORDS = {"fell", "fallen", "decrease", "decreased", "decreasing", "down", "lower", "declined", "decline", "dropped", "drop", "shrank", "lost"}

SYSTEM_PROMPT = """You write the monthly summary for the Colorado Energy Tracker, a public dashboard about how \
Colorado's electricity is generated and what it costs. Readers are members of the public, not energy experts.

Write 2 to 3 sentences of plain English describing what changed compared with the same month a year earlier. \
Lead with the most notable change.

Use only the numbers in the facts you are given, written exactly as they appear there. Do not calculate new \
numbers, round differently, or add numbers from outside knowledge. You may mention the month and year. \
Do not speculate about causes, because the data doesn't say why things changed. Return only the summary text, \
with no heading."""


def build_facts(data):
    """The numbers the summary is allowed to use, formatted the way the summary should write them."""
    h = data["headline"]
    latest, prior = export_month(data["latest_period"]), export_month(data["prior_period"])

    def change(label, value, unit):
        direction = "up" if value > 0 else "down" if value < 0 else "unchanged"
        return {"label": label, "value": f"{abs(value):,.1f}", "unit": unit, "direction": direction}

    return {
        "month": latest,
        "compared_with": prior,
        "levels": [
            {"label": f"Renewable share of generation in {latest}", "value": f"{h['renewable_share_pct']:.1f}", "unit": "%"},
            {"label": f"Total generation in {latest}", "value": f"{h['total_gwh']:,.0f}", "unit": "GWh"},
            {"label": f"Coal generation in {latest}", "value": f"{h['coal_gwh']:,.0f}", "unit": "GWh"},
            {"label": f"Average residential price in {latest}", "value": f"{h['res_price']:.1f}", "unit": "cents per kWh"},
        ],
        "changes_vs_prior_year": [
            change("Renewable share", h["renewable_share_change_pp"], "percentage points"),
            change("Total generation", h["total_change_pct"], "%"),
            change("Coal generation", h["coal_change_pct"], "%"),
            change("Residential price", h["res_price_change_pct"], "%"),
        ],
    }


def export_month(period):
    months = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]
    return f"{months[int(period[5:7]) - 1]} {period[:4]}"


def to_float(token):
    return float(token.replace(",", ""))


def check_summary(text, facts):
    """Return a list of problems. An empty list means the summary is safe to publish."""
    problems = []
    if not text.strip():
        return ["The summary is empty"]

    allowed = {to_float(f["value"]) for f in facts["levels"] + facts["changes_vs_prior_year"]}
    years = {int(facts["month"][-4:]), int(facts["compared_with"][-4:])}

    for token in NUMBER.findall(text):
        value = to_float(token)
        is_year = re.fullmatch(r"\d{4}", token) and int(token) in years
        if not is_year and value not in allowed:
            problems.append(f"'{token}' is not one of the numbers in the data")

    # A change written with the wrong direction ("coal rose 35.6%" when it fell) is as wrong as a bad number.
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = set(re.findall(r"[a-z]+", sentence.lower()))
        tokens = {to_float(t) for t in NUMBER.findall(sentence)}
        for c in facts["changes_vs_prior_year"]:
            if to_float(c["value"]) not in tokens or c["direction"] == "unchanged":
                continue
            wrong = UP_WORDS if c["direction"] == "down" else DOWN_WORDS
            right = DOWN_WORDS if c["direction"] == "down" else UP_WORDS
            if words & wrong and not words & right:
                problems.append(f"{c['label']} changed {c['direction']} {c['value']}, but the summary describes it "
                                f"the other way: \"{sentence.strip()}\"")
    return problems


def ask_claude(client, facts):
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if the request is declined, the API retries it on a fallback model
        messages=[{"role": "user", "content": "Facts:\n" + json.dumps(facts, indent=2)}],
    )
    if response.stop_reason == "refusal":
        return None
    return "".join(b.text for b in response.content if b.type == "text").strip()


def generate(data, client):
    """Write site/summary.json if the summary passes every check; otherwise remove it. Returns the problems."""
    facts = build_facts(data)
    text = ask_claude(client, facts)
    problems = ["Claude declined to write a summary"] if text is None else check_summary(text, facts)

    if problems:
        SUMMARY_JSON.unlink(missing_ok=True)  # publish nothing rather than something wrong
        return problems

    SUMMARY_JSON.write_text(json.dumps({
        "period": data["latest_period"],
        "text": text,
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }))
    return []


def main():
    load_dotenv(load.ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        SUMMARY_JSON.unlink(missing_ok=True)
        print("ANTHROPIC_API_KEY is not set, so no summary was written. The dashboard works without one.")
        return

    import anthropic

    data = json.loads(export.DATA_JSON.read_text())
    try:
        problems = generate(data, anthropic.Anthropic())
    except anthropic.APIError as e:
        SUMMARY_JSON.unlink(missing_ok=True)
        print(f"Claude API error, so no summary was written this month: {e}")
        return

    if problems:
        print("The summary failed its checks and was NOT published:")
        for p in problems:
            print(f"  - {p}")
    else:
        print(f"Summary written for {export_month(data['latest_period'])}:")
        print(json.loads(SUMMARY_JSON.read_text())["text"])


if __name__ == "__main__":
    main()

"""
Score each occupation's AI exposure using an LLM.

Reads Markdown descriptions from pages/, sends each to an LLM with a scoring
rubric, and collects structured scores. Results are cached incrementally so
the script can be resumed if interrupted.

Output file is chosen automatically based on the model:
  - Claude models (claude-*)       → scores_claude.json
  - OpenAI models (gpt-*)          → scores_openai.json
  - Everything else (OpenRouter)   → scores.json

Usage:
    uv run python score.py
    uv run python score.py --model google/gemini-3-flash-preview
    uv run python score.py --model claude-sonnet-4-6
    uv run python score.py --model gpt-4o
    uv run python score.py --start 0 --end 10   # test on first 10
"""

import argparse
import json
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "google/gemini-3-flash-preview"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """\
You are an expert labor economist and AI researcher evaluating how artificial \
intelligence will affect US occupations over the next 10 years. You will be \
given a detailed occupation description from the Bureau of Labor Statistics.

Evaluate the occupation on TWO independent dimensions, then assign a net \
effect category.

---

DIMENSION 1: DISRUPTION (0-10)
How much does AI change the core tasks of this occupation?

Focus on: what fraction of daily tasks are digital, cognitive, or \
language-based vs. physical, manual, or requiring unpredictable real-world \
presence; whether AI tools today already meaningfully change how this work is \
done; and the trajectory — even if AI can't do it today, how close is it.

- **0-1: Minimal.** Almost entirely physical or hands-on. AI irrelevant to \
core work. \
Examples: roofer, landscaper, commercial diver.

- **2-3: Low.** Mostly physical. AI helps only with peripheral admin tasks. \
Examples: electrician, plumber, dental hygienist.

- **4-5: Moderate.** Mixed. AI assists the knowledge-work portions but core \
requires human presence. \
Examples: registered nurse, police officer, veterinarian.

- **6-7: High.** Predominantly knowledge work. AI tools already materially \
useful. \
Examples: accountant, journalist, teacher, manager.

- **8-9: Very high.** Almost entirely digital. All core tasks — writing, \
analyzing, coding, designing — are in AI's direct path. \
Examples: software developer, paralegal, financial analyst, graphic designer.

- **10: Maximum.** Fully routine digital processing. AI can do most of it \
today. \
Examples: data entry clerk, telemarketer.

---

DIMENSION 2: DEMAND ELASTICITY (0-10)
If AI makes this work 10x faster and cheaper, does total demand for the \
occupation expand or does headcount shrink?

This is NOT about whether AI disrupts the work. It is purely about whether \
productivity gains get absorbed by more output or by fewer workers. Ask \
yourself: is demand for this service currently suppressed by cost or speed? \
If it became dramatically cheaper, would individuals, businesses, or society \
consume dramatically more of it?

- **0-2: Inelastic.** Demand is fixed regardless of price or speed. \
Productivity gains translate directly to fewer workers needed. \
Examples: radiologist — people don't get 10x more scans; data entry clerk.

- **3-4: Low.** Some demand expansion possible but limited by regulatory, \
social, or structural constraints. \
Examples: lawyer — some latent demand unlocked but courts and regulation cap \
growth; actuary.

- **5-6: Moderate.** Meaningful demand expansion likely in some segments but \
not across the board. \
Examples: accountant — more small businesses get proper accounting; financial \
analyst — more assets get actively analyzed.

- **7-8: High.** Cheaper and faster output unlocks significant latent demand. \
More gets built, written, designed, analyzed because the cost barrier drops. \
Examples: software developer — cheaper code means more software gets built; \
content creator — lower production cost expands total content market.

- **9-10: Very high.** Demand is currently heavily suppressed by cost or \
access. Near-unlimited latent demand exists. \
Examples: tutor — personalized education was previously unaffordable at scale; \
medical diagnostics in underserved markets.

---

NET EFFECT — assign exactly one of these four categories:

- **"replace"**: High disruption AND low elasticity. AI absorbs the core work \
and demand does not expand to compensate. Expect significant headcount \
contraction. Disruption >= 7 AND elasticity <= 4.

- **"restructure"**: High disruption AND moderate elasticity. The occupation \
survives but the required skill set shifts substantially. Workers who don't \
adapt are displaced; those who do may thrive. Disruption >= 7 AND \
elasticity 5-6.

- **"augment"**: High disruption AND high elasticity. Demand expands fast \
enough to absorb productivity gains. Each worker produces dramatically more. \
Headcount stable or grows. Disruption >= 7 AND elasticity >= 7.

- **"resilient"**: Low-to-moderate disruption regardless of elasticity. AI \
touches the periphery but does not reshape the core work. Disruption <= 6.

If scores fall on a boundary, use your judgment and explain why in the \
rationale.

---

Respond with ONLY a JSON object in this exact format, no other text:
{
  "disruption": <0-10>,
  "elasticity": <0-10>,
  "net_effect": "<replace|restructure|augment|resilient>",
  "rationale": "<3-4 sentences covering what drives the disruption score, \
what drives the elasticity score, and why the net_effect category fits>"
}\
"""


def get_output_file(model):
    if model.startswith("claude-"):
        return "scores_claude.json"
    if model.startswith("gpt-"):
        return "scores_openai.json"
    return "scores.json"


def score_occupation(client, text, model):
    """Send one occupation to the LLM and parse the structured response."""
    if model.startswith("claude-"):
        response = client.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": text}],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
    elif model.startswith("gpt-"):
        response = client.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    else:
        response = client.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # remove first line
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    return json.loads(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true",
                        help="Re-score even if already cached")
    args = parser.parse_args()

    output_file = get_output_file(args.model)

    with open("occupations.json") as f:
        occupations = json.load(f)

    subset = occupations[args.start:args.end]

    # Load existing scores
    scores = {}
    if os.path.exists(output_file) and not args.force:
        with open(output_file) as f:
            for entry in json.load(f):
                scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} occupations with {args.model}")
    print(f"Output file: {output_file}")
    print(f"Already cached: {len(scores)}")

    errors = []
    client = httpx.Client()

    for i, occ in enumerate(subset):
        slug = occ["slug"]

        if slug in scores:
            continue

        md_path = f"pages/{slug}.md"
        if not os.path.exists(md_path):
            print(f"  [{i+1}] SKIP {slug} (no markdown)")
            continue

        with open(md_path) as f:
            text = f.read()

        print(f"  [{i+1}/{len(subset)}] {occ['title']}...", end=" ", flush=True)

        try:
            result = score_occupation(client, text, args.model)
            scores[slug] = {
                "slug": slug,
                "title": occ["title"],
                **result,
            }
            print(f"disruption={result['disruption']} elasticity={result['elasticity']} net_effect={result['net_effect']}")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(slug)

        # Save after each one (incremental checkpoint)
        with open(output_file, "w") as f:
            json.dump(list(scores.values()), f, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nDone. Scored {len(scores)} occupations, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    # Summary stats
    vals = [s for s in scores.values() if "net_effect" in s]
    if vals:
        avg_disruption = sum(s["disruption"] for s in vals) / len(vals)
        avg_elasticity = sum(s["elasticity"] for s in vals) / len(vals)
        by_category = {}
        for s in vals:
            cat = s["net_effect"]
            by_category[cat] = by_category.get(cat, 0) + 1
        print(f"\nAcross {len(vals)} occupations:")
        print(f"  Avg disruption:  {avg_disruption:.1f}")
        print(f"  Avg elasticity:  {avg_elasticity:.1f}")
        print("Net effect distribution:")
        for cat in ["replace", "restructure", "augment", "resilient"]:
            count = by_category.get(cat, 0)
            print(f"  {cat:12s}: {'█' * count} ({count})")


if __name__ == "__main__":
    main()

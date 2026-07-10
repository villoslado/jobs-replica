"""
Aggregate site/data.json into summary statistics and a contested list.

Outputs:
  summary_jobs.csv  — job counts by net_effect category per model (millions)
  summary_comp.csv  — burdened comp by net_effect category per model (trillions)
  contested.csv     — occupations where models disagree

Usage:
    uv run python aggregate.py
"""

import csv
import json

CATEGORIES = ["replace", "restructure", "augment", "resilient"]
MODELS = ["claude", "opus", "openai", "gpt55", "gpt56sol", "fable5", "grok45"]

COLUMNS = [
    ("claude_sonnet", "Claude Sonnet 4.6"),
    ("claude_opus", "Claude Opus 4.8"),
    ("claude_avg", "Claude Avg"),
    ("gpt4o", "GPT-4o"),
    ("gpt55", "GPT-5.5"),
    ("gpt56sol", "GPT-5.6 Sol"),
    ("fable5", "Claude Fable 5"),
    ("grok45", "Grok 4.5"),
    ("gpt_avg", "GPT Avg"),
    ("grand_avg", "Grand Avg"),
]


def fmt_jobs(n):
    if n is None:
        return "N/A"
    return f"{n / 1e6:.1f}M"


def fmt_comp(n):
    if n is None:
        return "N/A"
    return f"{n / 1e12:.2f}T"


def print_table(title, rows, fmt_fn, col_width=11):
    label_w = 18
    col_labels = [label for _, label in COLUMNS]
    col_keys = [key for key, _ in COLUMNS]

    header = f"{'':>{label_w}}  " + "  ".join(f"{c:>{col_width}}" for c in col_labels)
    sep = "-" * len(header)
    thick = "=" * len(header)

    print(f"\n{title}")
    print(sep)
    print(header)
    print(sep)

    for row in rows:
        label = row["label"]
        vals = [fmt_fn(row[k]) for k in col_keys]
        if row.get("is_total"):
            print(thick)
        elif row.get("is_separator"):
            print(sep)
        print(f"{label:<{label_w}}  " + "  ".join(f"{v:>{col_width}}" for v in vals))


def build_csv_rows(rows, fmt_fn):
    csv_rows = []
    for row in rows:
        out = {"net_effect": row["label"].strip()}
        for key, header in COLUMNS:
            out[header] = fmt_fn(row[key])
        csv_rows.append(out)
    return csv_rows


def main():
    with open("site/data.json") as f:
        data = json.load(f)

    totals = {m: {cat: {"jobs": 0, "comp": 0} for cat in CATEGORIES} for m in MODELS}

    for occ in data:
        jobs = occ.get("jobs") or 0
        comp = occ.get("burdened_comp") or 0
        for model in MODELS:
            net = occ.get(f"{model}_net_effect")
            if net in CATEGORIES:
                totals[model][net]["jobs"] += jobs
                totals[model][net]["comp"] += comp

    exposed_cats = ["augment", "restructure", "replace"]

    def model_val(model, row_label, key):
        if row_label == "Resilient":
            return totals[model]["resilient"][key]
        if row_label == "Total Exposed":
            return sum(totals[model][c][key] for c in exposed_cats)
        if row_label == "Total":
            return totals[model]["resilient"][key] + sum(
                totals[model][c][key] for c in exposed_cats
            )
        return totals[model][row_label.lower()][key]

    row_specs = [
        ("Resilient", False, False),
        ("Total Exposed", True, False),
        ("  Augment", False, False),
        ("  Restructure", False, False),
        ("  Replace", False, False),
        ("Total", False, True),
    ]

    def build_rows(key):
        out = []
        for label, is_sep, is_total in row_specs:
            inner = label.strip()
            sonnet = model_val("claude", inner, key)
            opus = model_val("opus", inner, key)
            gpt4o = model_val("openai", inner, key)
            gpt55 = model_val("gpt55", inner, key)
            gpt56sol = model_val("gpt56sol", inner, key)
            fable5 = model_val("fable5", inner, key)
            grok45 = model_val("grok45", inner, key)
            claude_avg = (sonnet + opus) // 2
            gpt_avg = (gpt4o + gpt55 + gpt56sol) // 3
            grand_avg = (sonnet + opus + gpt4o + gpt55 + gpt56sol + fable5 + grok45) // 7
            out.append({
                "label": label,
                "is_separator": is_sep,
                "is_total": is_total,
                "claude_sonnet": sonnet,
                "claude_opus": opus,
                "claude_avg": claude_avg,
                "gpt4o": gpt4o,
                "gpt55": gpt55,
                "gpt56sol": gpt56sol,
                "fable5": fable5,
                "grok45": grok45,
                "gpt_avg": gpt_avg,
                "grand_avg": grand_avg,
            })
        return out

    jobs_rows = build_rows("jobs")
    comp_rows = build_rows("comp")

    print_table("Table 1 — Jobs", jobs_rows, fmt_jobs)
    print_table("Table 2 — Fully-burdened compensation", comp_rows, fmt_comp)

    csv_fields = ["net_effect"] + [header for _, header in COLUMNS]

    with open("summary_jobs.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(build_csv_rows(jobs_rows, fmt_jobs))
    print("\nWrote summary_jobs.csv")

    with open("summary_comp.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(build_csv_rows(comp_rows, fmt_comp))
    print("Wrote summary_comp.csv")

    contested = [occ for occ in data if occ.get("contested")]
    contested_fields = ["title", "category"]
    for m in MODELS:
        contested_fields.extend([f"{m}_disruption", f"{m}_elasticity", f"{m}_net_effect"])
    with open("contested.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=contested_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(contested)
    print(f"Wrote contested.csv ({len(contested)} occupations)")


if __name__ == "__main__":
    main()

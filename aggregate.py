"""
Aggregate site/data.json into summary statistics and a contested list.

Outputs:
  summary_jobs.csv  — job counts by net_effect category per model (millions)
  summary_comp.csv  — burdened comp by net_effect category per model (trillions)
  contested.csv     — occupations where claude and openai disagree

Usage:
    uv run python aggregate.py
"""

import csv
import json

CATEGORIES = ["replace", "restructure", "augment", "resilient"]

ECI_BY_CATEGORY = {
    "management": 1.4942,
    "business-and-financial": 1.4942,
    "computer-and-information-technology": 1.4729,
    "architecture-and-engineering": 1.4729,
    "math": 1.4729,
    "life-physical-and-social-science": 1.4729,
    "legal": 1.4729,
    "community-and-social-service": 1.4729,
    "media-and-communication": 1.4729,
    "arts-and-design": 1.4729,
    "education-training-and-library": 1.4694,
    "healthcare": 1.5167,
    "protective-service": 1.3851,
    "food-preparation-and-serving": 1.3851,
    "building-and-grounds-cleaning": 1.3851,
    "personal-care-and-service": 1.3851,
    "sales": 1.3299,
    "office-and-administrative-support": 1.4970,
    "construction-and-extraction": 1.4747,
    "farming-fishing-and-forestry": 1.4747,
    "installation-maintenance-and-repair": 1.4745,
    "production": 1.4894,
    "transportation-and-material-moving": 1.4625,
    "entertainment-and-sports": 1.3851,
    "military": 1.6221,
}
FALLBACK_ECI = 1.4584


def load_karpathy():
    """Load scores.json and compute jobs/comp per bucket using occupations.csv stats."""
    with open("scores.json") as f:
        karp_scores = {s["slug"]: s["exposure"] for s in json.load(f)}

    with open("occupations.csv") as f:
        reader = csv.DictReader(f)
        occ_stats = {row["slug"]: row for row in reader}

    totals = {
        "high_exposure": {"jobs": 0, "comp": 0},
        "low_exposure": {"jobs": 0, "comp": 0},
    }

    for slug, exposure in karp_scores.items():
        occ = occ_stats.get(slug)
        if not occ:
            continue
        jobs = int(occ["num_jobs_2024"]) if occ["num_jobs_2024"] else None
        pay = int(occ["median_pay_annual"]) if occ["median_pay_annual"] else None
        if not jobs or not pay:
            continue
        eci = ECI_BY_CATEGORY.get(occ["category"], FALLBACK_ECI)
        comp = round(jobs * pay * eci)

        bucket = "high_exposure" if exposure >= 7 else "low_exposure"
        totals[bucket]["jobs"] += jobs
        totals[bucket]["comp"] += comp

    return totals


def fmt_jobs(n):
    """Format jobs value in millions, 1 decimal place."""
    if n is None:
        return "N/A"
    return f"{n / 1e6:.1f}M"


def fmt_comp(n):
    """Format comp value in trillions, 2 decimal places."""
    if n is None:
        return "N/A"
    return f"{n / 1e12:.2f}T"


def print_table(title, rows, val_key, fmt_fn, col_width=10):
    """Print a single-metric table."""
    col_labels = ["Claude", "GPT-4o", "Average", "Karpathy"]
    label_w = 18

    header = f"{'':>{label_w}}  " + "  ".join(f"{c:>{col_width}}" for c in col_labels)
    sep = "-" * len(header)
    thick = "=" * len(header)

    print(f"\n{title}")
    print(sep)
    print(header)
    print(sep)

    for row in rows:
        label = row["label"]
        vals = [
            fmt_fn(row[f"claude_{val_key}"]),
            fmt_fn(row[f"openai_{val_key}"]),
            fmt_fn(row[f"avg_{val_key}"]),
            fmt_fn(row[f"karpathy_{val_key}"]),
        ]
        if row.get("is_total"):
            print(thick)
        elif row.get("is_separator"):
            print(sep)
        print(f"{label:<{label_w}}  " + "  ".join(f"{v:>{col_width}}" for v in vals))


def build_csv_rows(rows, val_key, fmt_fn):
    """Build list of dicts for CSV output."""
    csv_rows = []
    for row in rows:
        csv_rows.append({
            "net_effect": row["label"].strip(),
            "claude": fmt_fn(row[f"claude_{val_key}"]),
            "gpt4o": fmt_fn(row[f"openai_{val_key}"]),
            "average": fmt_fn(row[f"avg_{val_key}"]),
            "karpathy": fmt_fn(row[f"karpathy_{val_key}"]),
        })
    return csv_rows


def main():
    with open("site/data.json") as f:
        data = json.load(f)

    karp = load_karpathy()

    # Accumulators: {model: {net_effect: {jobs, comp}}}
    totals = {
        "claude": {cat: {"jobs": 0, "comp": 0} for cat in CATEGORIES},
        "openai": {cat: {"jobs": 0, "comp": 0} for cat in CATEGORIES},
    }

    for occ in data:
        jobs = occ.get("jobs") or 0
        comp = occ.get("burdened_comp") or 0
        for model in ("claude", "openai"):
            net = occ.get(f"{model}_net_effect")
            if net in CATEGORIES:
                totals[model][net]["jobs"] += jobs
                totals[model][net]["comp"] += comp

    def avg(model_a, model_b, cat, key):
        return (totals[model_a][cat][key] + totals[model_b][cat][key]) // 2

    exposed_cats = ["augment", "restructure", "replace"]

    def sum_exposed(model, key):
        return sum(totals[model][cat][key] for cat in exposed_cats)

    c_exp_jobs = sum_exposed("claude", "jobs")
    c_exp_comp = sum_exposed("claude", "comp")
    o_exp_jobs = sum_exposed("openai", "jobs")
    o_exp_comp = sum_exposed("openai", "comp")

    # Grand total (resilient + exposed sub-cats, no double-counting total_exposed)
    c_total_jobs = totals["claude"]["resilient"]["jobs"] + c_exp_jobs
    c_total_comp = totals["claude"]["resilient"]["comp"] + c_exp_comp
    o_total_jobs = totals["openai"]["resilient"]["jobs"] + o_exp_jobs
    o_total_comp = totals["openai"]["resilient"]["comp"] + o_exp_comp
    karp_total_jobs = karp["high_exposure"]["jobs"] + karp["low_exposure"]["jobs"]
    karp_total_comp = karp["high_exposure"]["comp"] + karp["low_exposure"]["comp"]

    # Display row order:
    # 1. Resilient
    # 2. Total Exposed  (separator before)
    # 3.   Augment      (indented, Karpathy N/A)
    # 4.   Restructure  (indented, Karpathy N/A)
    # 5.   Replace      (indented, Karpathy N/A)
    # 6. Total          (thick separator before)

    display_rows = [
        {
            "label": "Resilient",
            "claude_jobs": totals["claude"]["resilient"]["jobs"],
            "openai_jobs": totals["openai"]["resilient"]["jobs"],
            "avg_jobs": avg("claude", "openai", "resilient", "jobs"),
            "karpathy_jobs": karp["low_exposure"]["jobs"],
            "claude_comp": totals["claude"]["resilient"]["comp"],
            "openai_comp": totals["openai"]["resilient"]["comp"],
            "avg_comp": avg("claude", "openai", "resilient", "comp"),
            "karpathy_comp": karp["low_exposure"]["comp"],
            "is_separator": False,
            "is_total": False,
        },
        {
            "label": "Total Exposed",
            "claude_jobs": c_exp_jobs,
            "openai_jobs": o_exp_jobs,
            "avg_jobs": (c_exp_jobs + o_exp_jobs) // 2,
            "karpathy_jobs": karp["high_exposure"]["jobs"],
            "claude_comp": c_exp_comp,
            "openai_comp": o_exp_comp,
            "avg_comp": (c_exp_comp + o_exp_comp) // 2,
            "karpathy_comp": karp["high_exposure"]["comp"],
            "is_separator": True,
            "is_total": False,
        },
        {
            "label": "  Augment",
            "claude_jobs": totals["claude"]["augment"]["jobs"],
            "openai_jobs": totals["openai"]["augment"]["jobs"],
            "avg_jobs": avg("claude", "openai", "augment", "jobs"),
            "karpathy_jobs": None,
            "claude_comp": totals["claude"]["augment"]["comp"],
            "openai_comp": totals["openai"]["augment"]["comp"],
            "avg_comp": avg("claude", "openai", "augment", "comp"),
            "karpathy_comp": None,
            "is_separator": False,
            "is_total": False,
        },
        {
            "label": "  Restructure",
            "claude_jobs": totals["claude"]["restructure"]["jobs"],
            "openai_jobs": totals["openai"]["restructure"]["jobs"],
            "avg_jobs": avg("claude", "openai", "restructure", "jobs"),
            "karpathy_jobs": None,
            "claude_comp": totals["claude"]["restructure"]["comp"],
            "openai_comp": totals["openai"]["restructure"]["comp"],
            "avg_comp": avg("claude", "openai", "restructure", "comp"),
            "karpathy_comp": None,
            "is_separator": False,
            "is_total": False,
        },
        {
            "label": "  Replace",
            "claude_jobs": totals["claude"]["replace"]["jobs"],
            "openai_jobs": totals["openai"]["replace"]["jobs"],
            "avg_jobs": avg("claude", "openai", "replace", "jobs"),
            "karpathy_jobs": None,
            "claude_comp": totals["claude"]["replace"]["comp"],
            "openai_comp": totals["openai"]["replace"]["comp"],
            "avg_comp": avg("claude", "openai", "replace", "comp"),
            "karpathy_comp": None,
            "is_separator": False,
            "is_total": False,
        },
        {
            "label": "Total",
            "claude_jobs": c_total_jobs,
            "openai_jobs": o_total_jobs,
            "avg_jobs": (c_total_jobs + o_total_jobs) // 2,
            "karpathy_jobs": karp_total_jobs,
            "claude_comp": c_total_comp,
            "openai_comp": o_total_comp,
            "avg_comp": (c_total_comp + o_total_comp) // 2,
            "karpathy_comp": karp_total_comp,
            "is_separator": False,
            "is_total": True,
        },
    ]

    # Print tables
    print_table("Table 1 — Jobs", display_rows, "jobs", fmt_jobs)
    print_table("Table 2 — Fully-burdened compensation", display_rows, "comp", fmt_comp)

    # Write CSVs
    csv_fields = ["net_effect", "claude", "gpt4o", "average", "karpathy"]

    jobs_rows = build_csv_rows(display_rows, "jobs", fmt_jobs)
    with open("summary_jobs.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(jobs_rows)
    print("\nWrote summary_jobs.csv")

    comp_rows = build_csv_rows(display_rows, "comp", fmt_comp)
    with open("summary_comp.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(comp_rows)
    print("Wrote summary_comp.csv")

    # Write contested.csv
    contested = [occ for occ in data if occ.get("contested")]
    contested_fields = [
        "title", "category",
        "claude_disruption", "claude_elasticity", "claude_net_effect",
        "openai_disruption", "openai_elasticity", "openai_net_effect",
    ]
    with open("contested.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=contested_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(contested)
    print(f"Wrote contested.csv ({len(contested)} occupations)")


if __name__ == "__main__":
    main()

"""
Aggregate site/data.json into summary statistics and a contested list.

Outputs:
  summary.csv   — job counts and burdened comp by net_effect category per model
  contested.csv — occupations where claude and openai disagree

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

    # Build per-category rows (replace / restructure / augment / resilient)
    summary_rows = []
    for cat in CATEGORIES:
        c = totals["claude"][cat]
        o = totals["openai"][cat]
        avg_jobs = (c["jobs"] + o["jobs"]) // 2
        avg_comp = (c["comp"] + o["comp"]) // 2
        # Karpathy doesn't split into these sub-buckets
        summary_rows.append({
            "net_effect": cat,
            "claude_jobs": c["jobs"],
            "claude_burdened_comp": c["comp"],
            "openai_jobs": o["jobs"],
            "openai_burdened_comp": o["comp"],
            "avg_jobs": avg_jobs,
            "avg_burdened_comp": avg_comp,
            "karpathy_jobs": "",
            "karpathy_burdened_comp": "",
        })

    # total_exposed row: replace + restructure + augment for claude/openai; high_exposure for Karpathy
    exposed_cats = ["replace", "restructure", "augment"]

    def sum_cat(model, key):
        return sum(totals[model][cat][key] for cat in exposed_cats)

    c_exp_jobs = sum_cat("claude", "jobs")
    c_exp_comp = sum_cat("claude", "comp")
    o_exp_jobs = sum_cat("openai", "jobs")
    o_exp_comp = sum_cat("openai", "comp")
    summary_rows.append({
        "net_effect": "total_exposed",
        "claude_jobs": c_exp_jobs,
        "claude_burdened_comp": c_exp_comp,
        "openai_jobs": o_exp_jobs,
        "openai_burdened_comp": o_exp_comp,
        "avg_jobs": (c_exp_jobs + o_exp_jobs) // 2,
        "avg_burdened_comp": (c_exp_comp + o_exp_comp) // 2,
        "karpathy_jobs": karp["high_exposure"]["jobs"],
        "karpathy_burdened_comp": karp["high_exposure"]["comp"],
    })

    # Populate resilient row's Karpathy numbers
    for row in summary_rows:
        if row["net_effect"] == "resilient":
            row["karpathy_jobs"] = karp["low_exposure"]["jobs"]
            row["karpathy_burdened_comp"] = karp["low_exposure"]["comp"]

    # Grand total row — exclude total_exposed to avoid double-counting
    def col_sum(key):
        return sum(r[key] for r in summary_rows if isinstance(r[key], int) and r["net_effect"] != "total_exposed")

    karp_total_jobs = karp["high_exposure"]["jobs"] + karp["low_exposure"]["jobs"]
    karp_total_comp = karp["high_exposure"]["comp"] + karp["low_exposure"]["comp"]
    summary_rows.append({
        "net_effect": "Total",
        "claude_jobs": col_sum("claude_jobs"),
        "claude_burdened_comp": col_sum("claude_burdened_comp"),
        "openai_jobs": col_sum("openai_jobs"),
        "openai_burdened_comp": col_sum("openai_burdened_comp"),
        "avg_jobs": col_sum("avg_jobs"),
        "avg_burdened_comp": col_sum("avg_burdened_comp"),
        "karpathy_jobs": karp_total_jobs,
        "karpathy_burdened_comp": karp_total_comp,
    })

    # Write summary.csv
    fieldnames = [
        "net_effect",
        "claude_jobs", "claude_burdened_comp",
        "openai_jobs", "openai_burdened_comp",
        "avg_jobs", "avg_burdened_comp",
        "karpathy_jobs", "karpathy_burdened_comp",
    ]
    with open("summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
    print("Wrote summary.csv")

    # Print table to console
    def fmt_jobs(n):
        if n == "" or n is None:
            return f"{'N/A':>12}"
        return f"{n:>12,}"

    def fmt_comp(n):
        if n == "" or n is None:
            return f"{'N/A':>10}"
        return f"${n / 1e12:>8.2f}T" if n >= 1e12 else f"${n / 1e9:>8.1f}B"

    header = (
        f"{'net_effect':<14}  {'claude_jobs':>12}  {'claude_comp':>10}  "
        f"{'openai_jobs':>12}  {'openai_comp':>10}  {'avg_jobs':>12}  {'avg_comp':>10}  "
        f"{'karpathy_jobs':>13}  {'karpathy_comp':>13}"
    )
    print()
    print(header)
    print("-" * len(header))
    for row in summary_rows:
        if row["net_effect"] == "Total":
            print("=" * len(header))
        elif row["net_effect"] == "total_exposed":
            print("-" * len(header))
        print(
            f"{row['net_effect']:<14}  "
            f"{fmt_jobs(row['claude_jobs'])}  "
            f"{fmt_comp(row['claude_burdened_comp']):>10}  "
            f"{fmt_jobs(row['openai_jobs'])}  "
            f"{fmt_comp(row['openai_burdened_comp']):>10}  "
            f"{fmt_jobs(row['avg_jobs'])}  "
            f"{fmt_comp(row['avg_burdened_comp']):>10}  "
            f"{fmt_jobs(row['karpathy_jobs']):>13}  "
            f"{fmt_comp(row['karpathy_burdened_comp']):>13}"
        )

    # Write contested.csv
    contested = [
        occ for occ in data if occ.get("contested")
    ]
    contested_fields = [
        "title", "category",
        "claude_disruption", "claude_elasticity", "claude_net_effect",
        "openai_disruption", "openai_elasticity", "openai_net_effect",
    ]
    with open("contested.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=contested_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(contested)
    print(f"\nWrote contested.csv ({len(contested)} occupations)")


if __name__ == "__main__":
    main()

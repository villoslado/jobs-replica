"""
Build a compact JSON for the website by merging CSV stats with AI scores.

Reads occupations.csv (for stats), scores_claude.json, and scores_openai.json.
Writes site/data.json.

Usage:
    uv run python build_site_data.py
"""

import csv
import json
import os

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


def load_scores(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return {s["slug"]: s for s in json.load(f)}


def main():
    scores_claude = load_scores("scores_claude.json")
    scores_openai = load_scores("scores_openai.json")

    with open("occupations.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    data = []
    for row in rows:
        slug = row["slug"]
        category = row["category"]
        sc = scores_claude.get(slug, {})
        so = scores_openai.get(slug, {})

        pay = int(row["median_pay_annual"]) if row["median_pay_annual"] else None
        jobs = int(row["num_jobs_2024"]) if row["num_jobs_2024"] else None

        eci = ECI_BY_CATEGORY.get(category, FALLBACK_ECI)
        burdened_comp = round(jobs * pay * eci) if jobs and pay else None

        # Contested: net_effect disagrees OR disruption/elasticity differ by >= 2
        claude_net = sc.get("net_effect")
        openai_net = so.get("net_effect")
        claude_disruption = sc.get("disruption")
        openai_disruption = so.get("disruption")
        claude_elasticity = sc.get("elasticity")
        openai_elasticity = so.get("elasticity")

        contested = False
        if claude_net and openai_net:
            if claude_net != openai_net:
                contested = True
            if claude_disruption is not None and openai_disruption is not None:
                if abs(claude_disruption - openai_disruption) >= 2:
                    contested = True
            if claude_elasticity is not None and openai_elasticity is not None:
                if abs(claude_elasticity - openai_elasticity) >= 2:
                    contested = True

        data.append({
            "title": row["title"],
            "slug": slug,
            "category": category,
            "pay": pay,
            "jobs": jobs,
            "outlook": int(row["outlook_pct"]) if row["outlook_pct"] else None,
            "outlook_desc": row["outlook_desc"],
            "education": row["entry_education"],
            "url": row.get("url", ""),
            "burdened_comp": burdened_comp,
            "claude_disruption": claude_disruption,
            "claude_elasticity": claude_elasticity,
            "claude_net_effect": claude_net,
            "claude_rationale": sc.get("rationale"),
            "openai_disruption": openai_disruption,
            "openai_elasticity": openai_elasticity,
            "openai_net_effect": openai_net,
            "openai_rationale": so.get("rationale"),
            "contested": contested,
        })

    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w") as f:
        json.dump(data, f)

    print(f"Wrote {len(data)} occupations to site/data.json")
    total_jobs = sum(d["jobs"] for d in data if d["jobs"])
    print(f"Total jobs represented: {total_jobs:,}")
    contested_count = sum(1 for d in data if d["contested"])
    print(f"Contested occupations: {contested_count}")


if __name__ == "__main__":
    main()

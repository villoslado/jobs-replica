"""
Build a compact JSON for the website by merging CSV stats with AI scores.

Reads occupations.csv (for stats) and scores_claude.json, scores_opus.json,
scores_openai.json, scores_gpt55.json, scores_fable5.json. Writes site/data.json.

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
    model_scores = {
        "claude": load_scores("scores_claude.json"),
        "opus": load_scores("scores_opus.json"),
        "openai": load_scores("scores_openai.json"),
        "gpt55": load_scores("scores_gpt55.json"),
        "fable5": load_scores("scores_fable5.json"),
    }
    model_keys = list(model_scores.keys())

    with open("occupations.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    data = []
    for row in rows:
        slug = row["slug"]
        category = row["category"]
        per_model = {m: model_scores[m].get(slug, {}) for m in model_keys}

        pay = int(row["median_pay_annual"]) if row["median_pay_annual"] else None
        jobs = int(row["num_jobs_2024"]) if row["num_jobs_2024"] else None

        eci = ECI_BY_CATEGORY.get(category, FALLBACK_ECI)
        burdened_comp = round(jobs * pay * eci) if jobs and pay else None

        # Contested: any two models disagree on net_effect, or differ by >= 2
        # on disruption or elasticity.
        contested = False
        for i in range(len(model_keys)):
            for j in range(i + 1, len(model_keys)):
                a = per_model[model_keys[i]]
                b = per_model[model_keys[j]]
                a_net, b_net = a.get("net_effect"), b.get("net_effect")
                if not (a_net and b_net):
                    continue
                if a_net != b_net:
                    contested = True
                a_d, b_d = a.get("disruption"), b.get("disruption")
                if a_d is not None and b_d is not None and abs(a_d - b_d) >= 2:
                    contested = True
                a_e, b_e = a.get("elasticity"), b.get("elasticity")
                if a_e is not None and b_e is not None and abs(a_e - b_e) >= 2:
                    contested = True

        record = {
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
        }
        for m in model_keys:
            s = per_model[m]
            record[f"{m}_disruption"] = s.get("disruption")
            record[f"{m}_elasticity"] = s.get("elasticity")
            record[f"{m}_net_effect"] = s.get("net_effect")
            record[f"{m}_rationale"] = s.get("rationale")
        record["contested"] = contested
        data.append(record)

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

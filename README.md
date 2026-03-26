# US Labor AI Exposure Analysis

A research tool for analyzing and visualizing how artificial intelligence will
affect 342 US occupations across every sector of the economy. Built on Bureau
of Labor Statistics Occupational Outlook Handbook data, scored by two
independent LLMs (Claude Sonnet and GPT-4o), and visualized as an interactive
treemap.

> Forked from [karpathy/jobs](https://github.com/karpathy/jobs) and extended
> with a two-dimensional scoring framework, dual-model comparison, and
> fully-burdened labor cost exposure analysis.

---

## What This Is

This is a research and data exploration tool — not a report, paper, or
economic forecast. It is designed to surface patterns in how AI may reshape
the US labor market, with explicit attention to the difference between
replacement and reshaping.

The core insight driving this fork: a single "AI exposure" score conflates two
very different outcomes. A radiologist and a software developer may both score
high on AI disruption — but their futures look completely different. This
project separates those outcomes explicitly.

---

## The Framework

Each of the 342 BLS occupations is scored on two independent dimensions:

### Dimension 1 — Disruption (0–10)
How much does AI change the core tasks of this occupation? High scores
indicate digital, cognitive, language-based work that is directly in AI's
path. Low scores indicate physical, hands-on, or unpredictable real-world
work with a natural barrier to AI exposure.

### Dimension 2 — Demand Elasticity (0–10)
If AI makes this work 10x faster and cheaper, does total demand expand or
does headcount shrink? This is the dimension Karpathy's original framework
explicitly did not account for. High elasticity means productivity gains
unlock latent demand (more software gets built, more content gets created).
Low elasticity means productivity gains translate directly to fewer workers
needed.

### Net Effect Categories
The two dimensions combine into one of four outcome categories:

| Category | Meaning | Criteria |
|---|---|---|
| **Replace** | AI absorbs the core work. Significant headcount contraction expected. | Disruption ≥ 7, Elasticity ≤ 4 |
| **Restructure** | Role survives but required skills shift substantially. Workers who adapt thrive; those who don't are displaced. | Disruption ≥ 7, Elasticity 5–6 |
| **Augment** | Demand expands fast enough to absorb productivity gains. Each worker produces dramatically more. Headcount stable or grows. | Disruption ≥ 7, Elasticity ≥ 7 |
| **Resilient** | AI touches the periphery but does not reshape core work. | Disruption ≤ 6 |

---

## Dual-Model Scoring

The same prompt is run through two models independently:
- **Claude Sonnet** (`claude-sonnet-4-20250514`) → `scores_claude.json`
- **GPT-4o** (`gpt-4o`) → `scores_openai.json`

Occupations are flagged as **contested** when:
- The `net_effect` category differs between models, OR
- Disruption or elasticity scores differ by ≥ 2 points

Contested occupations are surfaced in the visualization and exported
separately in `contested.csv`. Model disagreement is itself a signal —
high disagreement likely indicates genuine uncertainty about an occupation's
AI trajectory.

---

## Dollar Exposure Analysis

Each occupation's exposure is quantified in fully-burdened labor cost terms:
```
burdened_comp = num_jobs × median_pay × ECI_multiplier
```

The ECI (Employer Cost Index) multiplier is sourced directly from the
**BLS Employer Costs for Employee Compensation, December 2025** report
(Table 2), applied at the occupational category level. This accounts for
benefits, payroll taxes, retirement, insurance, and legally required
contributions on top of base wages.

Results are aggregated by `net_effect` category and exported to
`summary.csv` with columns for Claude, GPT-4o, and blended average — giving
a range rather than a point estimate for the dollar figures.

---

## Data Pipeline
```
scrape.py          → html/           Raw BLS HTML pages (342 occupations)
process.py         → pages/          Clean Markdown versions
make_csv.py        → occupations.csv Structured fields (pay, jobs, outlook)
score.py           → scores_claude.json / scores_openai.json
build_site_data.py → site/data.json  Merged dataset for visualization
aggregate.py       → summary.csv + contested.csv
```

### Step by step
```bash
# 1. Scrape BLS pages (only needed once — results cached in html/)
uv run python scrape.py

# 2. Generate Markdown from HTML
uv run python process.py

# 3. Generate CSV summary
uv run python make_csv.py

# 4. Score with Claude Sonnet
uv run python score.py --model claude-sonnet-4-20250514

# 5. Score with GPT-4o
uv run python score.py --model gpt-4o

# 6. Build site data
uv run python build_site_data.py

# 7. Generate summary and contested tables
uv run python aggregate.py

# 8. Serve the visualization locally
cd site && python -m http.server 8000
```

---

## Key Files

| File | Description |
|---|---|
| `occupations.json` | Master list of 342 occupations with title, URL, category, slug |
| `occupations.csv` | Summary stats: pay, education, job count, growth projections |
| `scores_claude.json` | Claude Sonnet scores — disruption, elasticity, net_effect, rationale |
| `scores_openai.json` | GPT-4o scores — disruption, elasticity, net_effect, rationale |
| `site/data.json` | Merged dataset for the visualization frontend |
| `summary.csv` | Jobs and fully-burdened $ exposed by net_effect × model |
| `contested.csv` | Occupations where Claude and GPT-4o meaningfully disagree |
| `html/` | Raw HTML pages from BLS (~40MB, source of truth) |
| `pages/` | Clean Markdown versions of each occupation page |
| `site/` | Static website (treemap visualization) |

---

## Setup

Requires Python 3.10 (managed via pyenv) and `uv` for dependency management.
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python 3.10
pyenv install 3.10

# Install dependencies
uv sync
```

API keys required in `.env`:
```
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
```

---

## What This Is NOT

- It does not predict that a job will disappear. A **replace** verdict means
  AI is likely to absorb the core work and demand is unlikely to expand
  enough to compensate — not that every person in that role will lose their
  job overnight.
- It does not account for regulatory barriers, union protections, or social
  preferences for human workers in specific contexts.
- The scores are LLM estimates, not econometric forecasts. Two models are
  used precisely to surface uncertainty — where they agree, confidence is
  higher; where they disagree, the occupation warrants closer examination.
- The dollar figures represent fully-burdened labor cost *exposed* to AI
  disruption — not a prediction of how much will be eliminated or captured
  by AI vendors.

---

## Credits

Original data pipeline and visualization by
[Andrej Karpathy](https://github.com/karpathy/jobs). Extended with two-axis
scoring framework, dual-model comparison, BLS ECEC-sourced burden factors,
and dollar exposure aggregation.

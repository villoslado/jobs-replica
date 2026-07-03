# How Exposed Is the US Job Market to AI — and What Kind of Exposure?

A research tool for analyzing and visualizing how artificial intelligence will
affect 342 US occupations across every sector of the economy. Built on Bureau
of Labor Statistics Occupational Outlook Handbook data, scored by five
independent LLMs (Claude Sonnet 4.6, Claude Opus 4.8, GPT-4o, GPT-5.5, and
Claude Fable 5), and visualized as an interactive treemap.

> Forked from [karpathy/jobs](https://github.com/karpathy/jobs) and extended
> with a two-dimensional scoring framework, five-model comparison, and
> fully-burdened labor cost exposure analysis.

**Live site:** https://jobs-replica-production.up.railway.app/

---

## Disclaimer

This project is an experiment and should be interpreted as such.

- **LLMs make mistakes.** Claude Sonnet 4.6, Claude Opus 4.8, GPT-4o,
  GPT-5.5, and Claude Fable 5 are general-purpose language models, not labor
  economists. Their
  scores reflect patterns in training data, not rigorous economic analysis.
  They can be wrong, inconsistent, or biased in ways that are difficult to
  detect.
- **This is not a forecast.** Nothing in this project predicts what will
  happen to any occupation, worker, or industry. It is a structured way of
  asking five AI models how they reason about AI's impact on work — nothing
  more.
- **The framework is a simplification.** Real labor market dynamics involve
  regulatory environments, union protections, capital availability, adoption
  timelines, social preferences, and macroeconomic conditions that no
  two-dimensional scoring rubric can capture.
- **The dollar figures are illustrative.** Fully-burdened compensation
  figures represent labor cost associated with occupations in each category
  — not a prediction of job losses or productivity gains. They are a scale
  reference for the economic scale of AI exposure in productivity contexts,
  not a forecast.
- **Do not make decisions based on this.** This tool is not intended to
  inform hiring, investment, policy, or career decisions. If you are
  researching AI's impact on labor markets seriously, please consult
  peer-reviewed economic research.
- **Five models are better than one — but still not ground truth.** Using
  five models independently and surfacing disagreements adds a layer of
  robustness, but model agreement does not equal accuracy. All five models
  share training data biases and may systematically over- or underestimate
  AI's impact in certain domains.

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

## Five-Model Scoring

The same prompt is run through five models independently:
- **Claude Sonnet 4.6** (`claude-sonnet-4-6`) → `scores_claude.json`
- **Claude Opus 4.8** (`claude-opus-4-8`) → `scores_opus.json`
- **GPT-4o** (`gpt-4o`) → `scores_openai.json`
- **GPT-5.5** (`gpt-5.5`) → `scores_gpt55.json`
- **Claude Fable 5** (`claude-fable-5`) → `scores_fable5.json`

Occupations are flagged as **contested** when any two of the five models
disagree:
- The `net_effect` category differs between any two models, OR
- Disruption or elasticity scores differ by ≥ 2 points

**276 of 342 occupations** are flagged as contested. Contested occupations are
surfaced in the visualization and exported separately in `contested.csv`.
Model disagreement is itself a signal — high disagreement likely indicates
genuine uncertainty about an occupation's AI trajectory.

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
`summary.csv` with per-model columns — including a **Claude Fable 5** column —
and blended-average columns. The **Grand Avg** column averages all five models,
giving a range rather than a point estimate for the dollar figures. The figures
describe the economic scale of AI exposure in productivity contexts, not
predicted savings or losses.

---

## Data Pipeline
```
scrape.py          → html/           Raw BLS HTML pages (342 occupations)
process.py         → pages/          Clean Markdown versions
make_csv.py        → occupations.csv Structured fields (pay, jobs, outlook)
score.py           → scores_*.json   Per-model scores
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

# 4. Score with each model
uv run python score.py --model claude-sonnet-4-6
uv run python score.py --model claude-opus-4-8
uv run python score.py --model gpt-4o
uv run python score.py --model gpt-5.5
uv run python score.py --model claude-fable-5

# 5. Build site data
uv run python build_site_data.py

# 6. Generate summary and contested tables
uv run python aggregate.py

# 7. Serve the visualization locally
cd site && python -m http.server 8000
```

> **Note on `claude-fable-5`:** this model returns extended-thinking blocks, so
> its first response block is a `thinking` block rather than the answer. The
> `score.py` parser selects the first `text` block from the response content
> rather than assuming `content[0]`. Like `claude-opus-4-8`, its API call omits
> the `temperature` parameter.

---

## Key Files

| File | Description |
|---|---|
| `occupations.json` | Master list of 342 occupations with title, URL, category, slug |
| `occupations.csv` | Summary stats: pay, education, job count, growth projections |
| `scores_claude.json` | Claude Sonnet 4.6 scores — disruption, elasticity, net_effect, rationale |
| `scores_opus.json` | Claude Opus 4.8 scores — disruption, elasticity, net_effect, rationale |
| `scores_openai.json` | GPT-4o scores — disruption, elasticity, net_effect, rationale |
| `scores_gpt55.json` | GPT-5.5 scores — disruption, elasticity, net_effect, rationale |
| `scores_fable5.json` | Claude Fable 5 scores — disruption, elasticity, net_effect, rationale |
| `site/data.json` | Merged dataset for the visualization frontend |
| `summary.csv` | Jobs and fully-burdened $ exposed by net_effect × model |
| `contested.csv` | Occupations where any two of the five models meaningfully disagree |
| `html/` | Raw HTML pages from BLS (~40MB, source of truth) |
| `pages/` | Clean Markdown versions of each occupation page |
| `site/` | Static website (treemap visualization) |

---

## Methodology & Limitations

Three things to keep in mind when reading these results:

- **Not based on Acemoglu's model.** This analysis does not use an economic
  model. It is a structured prompt-engineering exercise — each BLS occupation
  description is sent to five AI models that score it on two dimensions.
  Acemoglu's work operates at the task level using economic viability
  thresholds; this analysis operates at the occupation level using LLM
  judgment. The approaches are complementary but distinct.
- **Does not account for relative labor price adjustments.** Wage levels are
  held constant at 2024 BLS medians. The analysis does not model wage
  compression in displaced occupations, wage inflation in augmented ones, or
  the rate at which falling AI costs shift the cost-effectiveness threshold
  for automation.
- **Scores structural direction, not economic viability or timing.** Net
  effect categories reflect the likely structural direction of AI's impact,
  not whether automation is cost-effective today or when it will arrive. They
  are a starting point for thinking, not a forecast.

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

## Credits

Original data pipeline and visualization by
[Andrej Karpathy](https://github.com/karpathy/jobs). Extended with two-axis
scoring framework, five-model comparison, BLS ECEC-sourced burden factors,
and dollar exposure aggregation.

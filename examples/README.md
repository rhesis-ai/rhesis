# Rhesis SDK Examples

Jupyter notebooks demonstrating key Rhesis SDK features and integrations.

## Notebooks

- **`end-to-end.ipynb`** - Complete workflow: generate, manage, execute, and evaluate tests
- **`config-synthesizer.ipynb`** - Structured test generation with ConfigSynthesizer
- **`metrics.ipynb`** - Custom evaluation metrics with CategoricalJudge and NumericJudge
- **`penelope/`** - Penelope testing framework examples (requires repo clone):
  - `endpoint-testing.ipynb` - Test live endpoints through Rhesis platform
  - `langchain-integration.ipynb` - Test LangChain chains and agents
  - `langgraph-integration.ipynb` - Test LangGraph agents and workflows

## Setup

**For SDK notebooks:**
1. Install dependencies: `pip install rhesis-sdk jupyter`
2. Get your API key from [rhesis.ai](https://rhesis.ai)
3. Set `RHESIS_API_KEY` in your environment or notebook

**For Penelope notebooks:**
1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Clone the repo: `git clone https://github.com/rhesis-ai/rhesis.git`
3. Set up environment: `cd rhesis/penelope && uv sync`
4. Install Jupyter: `uv pip install jupyter notebook ipykernel`
5. See individual notebooks for specific dependency requirements

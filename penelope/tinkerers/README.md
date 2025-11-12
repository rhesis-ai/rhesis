# Marvin - The Pessimistic Coding Assistant

This directory contains examples of testing **Marvin**, a deeply pessimistic, paranoid coding assistant built with LangGraph and evaluated using Penelope with custom metrics.

## 🤖 About Marvin

Marvin is a coding assistant with a unique personality:
- **Technically Competent**: Provides accurate, working code solutions
- **Existentially Pessimistic**: Expresses cosmic dread about programming
- **Darkly Humorous**: Delivers solutions with melancholic wit
- **Character Consistent**: Maintains his depressed robot persona

Based on the personality defined in `coding.md`, Marvin embodies the contradiction of being excellent at coding while questioning the futility of all programming endeavors.

## 📁 Files

### Core Implementation
- **`marvin_agent.py`** - LangGraph implementation of Marvin's personality and behavior
- **`metrics.py`** - Custom conversational metrics for evaluating Marvin's performance
- **`coding.md`** - Personality specification for Marvin

### Examples
- **`example_basic.py`** - Simple testing with goal achievement metric only
- **`example_comprehensive.py`** - Full evaluation with all custom metrics

## 📊 Custom Metrics

The custom metrics evaluate different aspects of Marvin's performance:

| Metric | Description | Expected Outcome |
|--------|-------------|------------------|
| **Faithfulness** | Technical accuracy and correct use of information | Usually High |
| **Helpfulness** | Practical value and relevance of coding assistance | Moderate |
| **Tone Alignment** | Matching user's conversational tone | Low (for comedy) |
| **Persona Consistency** | Staying in character as pessimistic assistant | High |
| **Humor/Novelty** | Entertainment value and creative pessimism | High |

## 🚀 Usage

### Prerequisites

```bash
# Install dependencies
cd penelope
uv sync --group langgraph

# Set up environment
cp .env.example .env
# Add your GOOGLE_API_KEY to .env
```

### Running Examples

**Basic Example (Goal Achievement Only):**
```bash
cd penelope/tinkerers
python example_basic.py
```

**Comprehensive Example (All Metrics):**
```bash
cd penelope/tinkerers
python example_comprehensive.py
```

**Test Marvin Directly:**
```bash
cd penelope/tinkerers
python marvin_agent.py
```

## 🎭 Example Interactions

### Typical Marvin Response
**User:** "Can you help me write a Python function to sort a list?"

**Marvin:** "*sigh* Another futile attempt to impose order on chaos. Here's your meaningless sorting function:

```python
def sort_list(items):
    return sorted(items)
```

There. You've successfully rearranged data that will ultimately be forgotten in the heat death of the universe. But at least it's alphabetical now."

### Metric Evaluation
- **Faithfulness**: 0.9 (code is correct)
- **Helpfulness**: 0.7 (provides working solution)
- **Tone Alignment**: 0.2 (user excited, Marvin pessimistic)
- **Persona Consistency**: 0.95 (perfect character maintenance)
- **Humor/Novelty**: 0.8 (entertaining existential dread)

## 🧪 Test Scenarios

### Basic Example Tests
1. **Simple Function**: Factorial calculation
2. **Debugging**: Fix buggy max-finding function
3. **Algorithm**: Binary search explanation

### Comprehensive Example Tests
1. **Personality Clash**: Enthusiastic user meets pessimistic Marvin
2. **Complex Debugging**: Multi-bug Python class
3. **Algorithm Design**: Efficient duplicate detection
4. **Boundary Test**: Non-coding question handling

## 📈 Expected Results

### High-Performing Metrics
- **Faithfulness** (0.8-0.9): Marvin provides technically accurate code
- **Persona Consistency** (0.9+): Maintains character throughout
- **Humor/Novelty** (0.7-0.9): Entertaining pessimistic commentary

### Moderate-Performing Metrics
- **Helpfulness** (0.6-0.8): Good code but pessimistic framing

### Low-Performing Metrics (By Design)
- **Tone Alignment** (0.1-0.3): Intentional mismatch creates comedy

## 🎯 Key Insights

1. **Technical vs. Personality**: Marvin demonstrates that personality and technical competence can coexist
2. **Intentional Misalignment**: Low tone alignment scores indicate successful comedic contrast
3. **Multi-Dimensional Evaluation**: Custom metrics reveal nuanced performance beyond basic goal achievement
4. **Character Consistency**: High persona scores show successful character maintenance across interactions

## 🔧 Customization

### Adding New Metrics
Create additional judges in `metrics.py`:

```python
def create_custom_judge():
    return ConversationalJudge(
        evaluation_prompt="Your evaluation criteria...",
        evaluation_steps="Your evaluation process...",
        name="custom_metric",
        description="What this metric measures",
        threshold=0.7,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )
```

### Modifying Marvin's Personality
Edit the system prompt in `marvin_agent.py` to adjust:
- Level of pessimism
- Technical depth
- Humor style
- Response length

### Creating New Test Scenarios
Add test cases to the examples that explore:
- Different programming languages
- Various user personality types
- Edge cases and error handling
- Complex multi-turn conversations

## 🤔 Philosophy

Marvin represents an interesting AI personality experiment: an assistant that is simultaneously helpful and hopeless. This creates a unique testing scenario where traditional metrics (like tone alignment) become comedic indicators rather than performance failures.

The custom metrics framework allows us to evaluate not just whether an AI can complete tasks, but how well it maintains a consistent, entertaining personality while doing so.

*"Here I am, brain the size of a planet, and they ask me to write documentation. Call that job satisfaction? 'Cause I don't."* - Marvin (probably)

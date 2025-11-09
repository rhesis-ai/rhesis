# SDK Metrics Refactoring Plan: Single-Turn vs Conversational

**Date:** November 7, 2025  
**Status:** Proposal  
**Goal:** Reduce code duplication between single-turn and conversational metrics implementations

---

## Executive Summary

After analyzing the SDK metrics implementation, we've identified **~600 lines of duplicate code** across single-turn and conversational metrics. The duplication exists at multiple levels: base classes, judge implementations, configurations, and evaluation patterns. This document outlines a phased refactoring approach to consolidate shared logic while maintaining backward compatibility.

**Key Finding:** The single-turn and conversational implementations are ~80-95% identical in their core logic, differing primarily in:
- Input validation (single-turn vs conversation parameters)
- Template variables (input/output/context vs conversation_text/goal)
- A few additional detail fields

---

## 1. Duplication Analysis

### 1.1 Base Class Duplication (HIGH PRIORITY)

**Files:**
- `sdk/metrics/base.py` (`BaseMetric`)
- `sdk/metrics/conversational/base.py` (`ConversationalMetricBase`)

**Duplicated Logic:**
```python
# Both classes have nearly identical:
- __init__ with config and model setup
- set_model / _set_model methods
- Property assignments (name, description, score_type, etc.)
- Model getter/setter patterns
```

**Lines of Duplication:** ~80 lines

---

### 1.2 Judge Base Duplication (CRITICAL - ~80% OVERLAP)

**Files:**
- `sdk/metrics/providers/native/base.py` (`JudgeBase`)
- `sdk/metrics/providers/native/conversational_judge.py` (`ConversationalJudge`)

**Duplication Table:**

| Method/Feature | JudgeBase | ConversationalJudge | Similarity | Lines |
|----------------|-----------|---------------------|------------|-------|
| `_validate_evaluate_inputs` | ✅ | ✅ | 90% | ~30 |
| `_get_base_details` | ✅ | ✅ | 100% | ~10 |
| `_handle_evaluation_error` | ✅ | ✅ | 100% | ~35 |
| `_setup_jinja_environment` | ✅ | ✅ | 100% | ~10 |
| `_get_prompt_template` | ✅ | ✅ | 80% | ~60 |
| `to_config` | ✅ | ✅ | 100% | ~5 |
| `from_config` | ✅ | ✅ | 100% | ~10 |
| `to_dict` | ✅ | ✅ | 100% | ~5 |
| `from_dict` | ✅ | ✅ | 100% | ~5 |
| `push` | ✅ | ✅ | 100% | ~10 |
| `pull` | ✅ | ✅ | 100% | ~30 |
| `__repr__` | ✅ | ✅ | 100% | ~3 |
| **TOTAL** | | | | **~213 lines** |

**Additional Duplication:**
- Config dataclass definitions (~40 lines)
- Initialization logic (~30 lines)
- Score evaluation logic (~15 lines)

**Total Duplication in Judge Bases:** ~**298 lines**

---

### 1.3 Config Duplication (HIGH PRIORITY)

**Files:**
- `sdk/metrics/providers/native/base.py` (`JudgeConfig`)
- `sdk/metrics/providers/native/conversational_judge.py` (`ConversationalJudgeConfig`)
- `sdk/metrics/providers/native/numeric_judge.py` (`NumericJudgeConfig`)

**Identical Base Fields:**
```python
@dataclass
class JudgeConfig(MetricConfig):
    evaluation_prompt: Optional[str] = None
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    evaluation_examples: Optional[str] = None
```

**Identical Numeric Scoring Fields & Validation:**
```python
# In both NumericJudgeConfig and ConversationalJudgeConfig:
min_score: Optional[float] = None
max_score: Optional[float] = None
threshold: Optional[float] = None
threshold_operator: Union[ThresholdOperator, str] = ...

def _validate_score_range(self, min_score, max_score) -> None:
    # 100% identical implementation in both

def _set_score_parameters(self, min_score, max_score, threshold) -> None:
    # 100% identical implementation in both
```

**Lines of Duplication:** ~100 lines

---

### 1.4 Concrete Metric Evaluation Pattern (MEDIUM PRIORITY)

**Comparison:** `NumericJudge.evaluate()` vs `GoalAchievementJudge.evaluate()`

**Pattern Structure (~95% identical):**

```python
def evaluate(self, <mode-specific-params>):
    # 1. Validation (different params, same pattern)
    self._validate_evaluate_inputs(...)
    
    # 2. Generate prompt (different template vars, same logic)
    prompt = self._get_prompt_template(...)
    
    # 3. Build details dict (98% identical)
    details = self._get_base_details(prompt)
    details.update({
        "threshold_operator": self.threshold_operator.value,
        "min_score": self.min_score,
        "max_score": self.max_score,
        "threshold": self.threshold,
        # Only difference: 2-3 mode-specific fields
    })
    
    # 4. Execute evaluation (100% identical)
    try:
        response = self.model.generate(prompt, schema=<ResponseSchema>)
        response = <ResponseSchema>(**response)
        score = response.score
        is_successful = self._evaluate_score(score)
        details.update({"score": score, "reason": response.reason, "is_successful": is_successful})
        return MetricResult(score=score, details=details)
    except Exception as e:
        return self._handle_evaluation_error(e, details, 0.0)
```

**Only Differences:**
1. Method signature (input params)
2. Response schema class name (but same structure)
3. 2-3 additional detail fields (e.g., `turn_count`, `goal`)

**Lines of Duplication:** ~80 lines per numeric judge pair

---

### 1.5 DeepEval Provider Duplication (MEDIUM PRIORITY)

**Files:**
- `sdk/metrics/providers/deepeval/metric_base.py` (`DeepEvalMetricBase`)
- `sdk/metrics/providers/deepeval/conversational_base.py` (`DeepEvalConversationalBase`)

**Duplicated Logic:**
- DeepEvalModelWrapper initialization and updates
- Model property getter/setter patterns
- `_metric` property management
- Model update propagation logic

**Lines of Duplication:** ~60 lines

---

### 1.6 Score Evaluation Logic (LOW PRIORITY)

**Both `NumericJudge` and `ConversationalJudge` have identical `_evaluate_score()` method:**

```python
def _evaluate_score(self, score: float) -> bool:
    threshold_operator = OPERATOR_MAP[self.threshold_operator]
    result = threshold_operator(score, self.threshold)
    return result
```

**Lines of Duplication:** ~10 lines

---

## 2. Total Duplication Summary

| Area | Lines | Priority | Risk Level |
|------|-------|----------|------------|
| Judge Base Classes | ~298 | CRITICAL | Medium |
| Config Classes | ~100 | HIGH | Low |
| Base Metric Classes | ~80 | HIGH | Medium |
| Evaluation Patterns | ~80 | MEDIUM | Low |
| DeepEval Providers | ~60 | MEDIUM | Medium |
| Misc Utilities | ~10 | LOW | Low |
| **TOTAL** | **~628 lines** | | |

---

## 3. Refactoring Strategy

### 3.1 Design Principles

1. **Backward Compatibility:** Existing metrics must continue to work
2. **DRY (Don't Repeat Yourself):** Share code, not copy it
3. **Single Responsibility:** Each class/module has one clear purpose
4. **Progressive Enhancement:** Phased approach, validate each step
5. **Test Coverage:** Comprehensive tests before and after each phase

### 3.2 Architectural Approach

**Option A: Composition (Recommended)**
- Create shared utility modules for identical logic
- Use composition/delegation pattern
- Keep existing class hierarchies mostly intact
- Lower risk, easier to implement

**Option B: Unified Base Class**
- Create single base class with "mode" parameter
- More radical refactoring
- Higher risk, but cleaner long-term
- Requires more careful design

**Recommendation:** Start with **Option A** for Phase 1-2, evaluate **Option B** for Phase 3

---

## 4. Phased Implementation Plan

### Phase 1: Extract Shared Utilities ⭐⭐⭐ ✅ COMPLETED
**Priority:** CRITICAL  
**Risk:** LOW  
**Estimated Time:** 2-3 hours  
**Lines Saved:** ~200  
**Status:** ✅ **COMPLETED** - All tests passing

#### Tasks:

1. **Create `sdk/metrics/providers/native/shared_utils.py`** ✅

   Extract 100% identical methods:
   ```python
   # From both JudgeBase and ConversationalJudge:
   - handle_evaluation_error()
   - get_base_details()
   - setup_jinja_environment()
   ```

2. **Create `sdk/metrics/providers/native/mixins.py`** ✅

   Consolidated module with both mixins:
   ```python
   # SerializationMixin:
   - to_config()
   - from_config()
   - to_dict()
   - from_dict()
   - __repr__()
   
   # BackendSyncMixin:
   - push()
   - pull()
   ```

4. **Update `JudgeBase` and `ConversationalJudge`**
   - Import and use shared utilities
   - Remove duplicate code
   - Add comprehensive tests

#### Success Criteria:
- ✅ All existing tests pass
- ✅ No behavior changes
- ✅ ~200 lines removed
- ✅ Shared code in single location

---

### Phase 2: Unified Config Hierarchy ⭐⭐ ✅ COMPLETED
**Priority:** HIGH  
**Risk:** MEDIUM  
**Estimated Time:** 3-4 hours  
**Lines Saved:** ~100  
**Status:** ✅ **COMPLETED** - All tests passing

#### Tasks:

1. **Create `sdk/metrics/providers/native/configs.py`** ✅

   ```python
   @dataclass
   class BaseJudgeConfig(MetricConfig):
       """Base config for all judge types"""
       evaluation_prompt: Optional[str] = None
       evaluation_steps: Optional[str] = None
       reasoning: Optional[str] = None
       evaluation_examples: Optional[str] = None
   
   
   # Shared validation functions
   def validate_score_range(min_score, max_score):
       # Single implementation
   
   def set_score_parameters(config, min_score, max_score, threshold):
       # Single implementation
   
   
   @dataclass
   class NumericJudgeConfig(BaseJudgeConfig):
       """Config for single-turn numeric judges"""
       min_score: Optional[float] = None
       max_score: Optional[float] = None
       threshold: Optional[float] = None
       threshold_operator: Union[ThresholdOperator, str] = ...
   
   
   @dataclass
   class ConversationalNumericConfig(BaseJudgeConfig):
       """Config for conversational numeric judges"""
       min_score: Optional[float] = None
       max_score: Optional[float] = None
       threshold: Optional[float] = None
       threshold_operator: Union[ThresholdOperator, str] = ...
   
   
   @dataclass
   class CategoricalJudgeConfig(BaseJudgeConfig):
       """Config for categorical judge metrics"""
       categories: Optional[List[str]] = None
       passing_categories: Optional[Union[str, List[str]]] = None
   ```

2. **Update all judge implementations** ✅ to use new config classes

3. **Add migration guide** for custom metrics

#### Success Criteria:
- ✅ All tests pass (32 passed, 1 skipped)
- ✅ Single source of truth for config classes in configs.py
- ✅ ~100 lines removed
- ✅ Easier to add new score types
- ✅ Backward compatibility maintained through aliases
- ✅ Consistent naming: configs.py contains *Config classes

---

### Phase 3: Evaluation Pattern Abstraction ⭐⭐
**Priority:** MEDIUM  
**Risk:** MEDIUM  
**Estimated Time:** 4-5 hours  
**Lines Saved:** ~80

#### Tasks:

1. **Create `sdk/metrics/providers/native/evaluation_patterns.py`**

   ```python
   class NumericEvaluationMixin:
       """Reusable numeric evaluation pattern"""
       
       def _execute_numeric_evaluation(
           self,
           prompt: str,
           response_schema: Type[BaseModel],
           base_details: Optional[Dict[str, Any]] = None,
           additional_details: Optional[Dict[str, Any]] = None,
       ) -> MetricResult:
           """
           Standard numeric evaluation workflow:
           1. Build details dict
           2. Generate with LLM + structured output
           3. Check threshold
           4. Return result or handle error
           """
           # Single implementation of the common pattern
   ```

2. **Update numeric judges** to use the pattern:

   ```python
   class NumericJudge(JudgeBase, NumericEvaluationMixin):
       def evaluate(self, input, output, expected_output, context):
           self._validate_evaluate_inputs(input, output, expected_output, context)
           prompt = self._get_prompt_template(input, output, expected_output, context)
           
           return self._execute_numeric_evaluation(
               prompt=prompt,
               response_schema=NumericScoreResponse,
               additional_details={}  # Mode-specific fields only
           )
   
   
   class GoalAchievementJudge(ConversationalJudge, NumericEvaluationMixin):
       def evaluate(self, conversation_history, goal):
           self._validate_evaluate_inputs(conversation_history, goal)
           prompt = self._get_prompt_template(conversation_history, goal)
           
           return self._execute_numeric_evaluation(
               prompt=prompt,
               response_schema=GoalAchievementScoreResponse,
               additional_details={
                   "turn_count": len(conversation_history),
                   "goal": goal or "Infer from conversation"
               }
           )
   ```

#### Success Criteria:
- ✅ All tests pass
- ✅ Evaluation pattern in single location
- ✅ Easy to add new numeric judges
- ✅ ~80 lines removed

---

### Phase 4: Unified Judge Base (Optional) ⭐
**Priority:** LOW (Nice to have)  
**Risk:** HIGH  
**Estimated Time:** 8-10 hours  
**Lines Saved:** ~150

#### Approach:

**Option A: Mode Parameter (Simpler)**
```python
class UnifiedJudgeBase(BaseMetric):
    """Single base for both single-turn and conversational"""
    
    def __init__(self, config, model, evaluation_mode='single_turn'):
        self.evaluation_mode = evaluation_mode
        # All shared initialization
        
    def _validate_inputs(self, *args, **kwargs):
        """Mode-aware validation"""
        if self.evaluation_mode == 'single_turn':
            return self._validate_single_turn(*args, **kwargs)
        else:
            return self._validate_conversational(*args, **kwargs)
```

**Option B: Protocol/ABC (More Flexible)**
```python
class EvaluationInput(Protocol):
    """Protocol for evaluation inputs"""
    def to_template_vars(self) -> Dict[str, Any]: ...
    def validate(self) -> None: ...


class SingleTurnInput(EvaluationInput):
    input: str
    output: str
    expected_output: Optional[str]
    context: Optional[List[str]]


class ConversationalInput(EvaluationInput):
    conversation_history: ConversationHistory
    goal: Optional[str]


class UnifiedJudgeBase(BaseMetric):
    def evaluate(self, evaluation_input: EvaluationInput) -> MetricResult:
        # Generic implementation using protocol
```

#### Decision Point:
- Evaluate after Phase 1-3 completion
- Measure complexity vs benefit
- Consider maintaining separate bases if unified adds complexity

---

### Phase 5: DeepEval Provider Unification (Optional)
**Priority:** LOW  
**Risk:** MEDIUM  
**Estimated Time:** 3-4 hours  
**Lines Saved:** ~60

Similar approach to native judges, but for DeepEval providers.

---

### Phase 6: Template Consolidation (Optional)
**Priority:** LOW  
**Risk:** LOW  
**Estimated Time:** 1-2 hours  
**Lines Saved:** ~20 (templates are cheap)

Templates could be unified with conditional blocks, but this is low priority since Jinja templates are easy to maintain separately.

---

## 5. Testing Strategy

### 5.1 Pre-Refactoring Tests

**Create comprehensive test suite covering:**
1. ✅ All single-turn judge types (numeric, categorical, binary)
2. ✅ All conversational judge types
3. ✅ DeepEval metrics (single-turn and conversational)
4. ✅ Serialization (to_dict, from_dict, to_config, from_config)
5. ✅ Backend sync (push, pull)
6. ✅ Error handling
7. ✅ Edge cases (missing values, invalid inputs)

### 5.2 Per-Phase Testing

**Each phase must:**
1. Pass all existing tests
2. Add new tests for shared utilities
3. Test backward compatibility
4. Performance regression testing

### 5.3 Integration Testing

**After all phases:**
1. End-to-end metric evaluation tests
2. Factory creation tests
3. Custom metric compatibility tests
4. Documentation examples verification

---

## 6. Migration Guide

### 6.1 For Internal Code

Most changes will be transparent. Key updates:
- Import paths may change for shared utilities
- Config classes may have new names (but same fields)

### 6.2 For External Users

**Backward Compatibility Promise:**
- All public APIs remain unchanged
- Existing metrics continue to work
- No breaking changes in Phase 1-3

**Deprecation Path (if needed for Phase 4):**
1. Deprecation warnings in version N
2. Documentation updates
3. Breaking changes only in major version N+1

### 6.3 For Custom Metrics

**Phase 1-2:** No changes needed  
**Phase 3:** May benefit from new evaluation patterns (optional)  
**Phase 4:** May need minor adjustments if unified base is adopted

---

## 7. Risk Mitigation

### 7.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Breaking existing metrics | HIGH | LOW | Comprehensive test suite |
| Performance regression | MEDIUM | LOW | Benchmark before/after |
| Increased complexity | MEDIUM | MEDIUM | Keep it simple, document well |
| Merge conflicts | LOW | MEDIUM | Small, focused PRs |

### 7.2 Process Risks

- **Timeline pressure:** Start with Phase 1 only, others are optional
- **Team bandwidth:** Each phase is independent and can be paused
- **Requirement changes:** Phased approach allows adaptation

---

## 8. Success Metrics

### 8.1 Quantitative

- ✅ **Lines of code reduced:** Target ~600 lines (Phase 1-3: ~380 lines)
- ✅ **Test coverage:** Maintain or increase (target: 90%+)
- ✅ **Performance:** No regression (< 5% variance acceptable)
- ✅ **Build time:** No increase

### 8.2 Qualitative

- ✅ **Code maintainability:** Easier to understand and modify
- ✅ **Developer experience:** Faster to add new metrics
- ✅ **Bug reduction:** Single source of truth = fewer bugs
- ✅ **Documentation clarity:** Simpler mental model

---

## 9. Timeline Estimate

| Phase | Duration | Dependencies | Can Skip? |
|-------|----------|--------------|-----------|
| Phase 1: Shared Utilities | 2-3 hours | None | ❌ (Critical) |
| Phase 2: Unified Configs | 3-4 hours | Phase 1 | ❌ (High value) |
| Phase 3: Evaluation Patterns | 4-5 hours | Phase 1-2 | ✅ (Nice to have) |
| Phase 4: Unified Base | 8-10 hours | Phase 1-3 | ✅ (Optional) |
| Phase 5: DeepEval | 3-4 hours | Phase 1 | ✅ (Optional) |
| Phase 6: Templates | 1-2 hours | None | ✅ (Low priority) |
| **Total (Core)** | **9-12 hours** | | |
| **Total (All)** | **21-28 hours** | | |

**Recommendation:** Start with **Phase 1-2** (5-7 hours), then evaluate next steps.

---

## 10. Next Steps

### Immediate Actions

1. ✅ Review this plan with team
2. ✅ Get approval for Phase 1
3. ✅ Create feature branch: `refactor/metrics-deduplication`
4. ✅ Set up comprehensive test suite
5. ✅ Begin Phase 1 implementation

### Decision Points

- **After Phase 1-2:** Evaluate value vs effort for Phase 3
- **After Phase 3:** Decide if Phase 4 (unified base) is worth the complexity
- **Ongoing:** Monitor for any new duplication patterns

### Future Considerations

- Apply similar patterns to other parts of SDK?
- Consider code generation for highly repetitive patterns?
- Document best practices for adding new metric types?

---

## 11. Questions & Discussion Topics

1. **Backward Compatibility:** What guarantees do we need for external users?
2. **Phase 4:** Is unified base class worth the complexity, or is composition enough?
3. **Testing:** What test coverage threshold is acceptable?
4. **Timeline:** Can we dedicate 1-2 sprints to this, or should it be incremental?
5. **Documentation:** When should we update docs (per phase or at the end)?

---

## Appendix A: File Structure (Proposed)

```
sdk/metrics/
├── base.py                          # Unified or keep separate?
├── conversational/
│   ├── base.py                     # Unified or keep separate?
│   └── types.py                    # Keep as-is
├── providers/
│   └── native/
│       ├── base.py                 # ✅ Slimmed down (Phase 1)
│       ├── conversational_judge.py # ✅ Slimmed down (Phase 1 & 2)
│       ├── numeric_judge.py        # ✅ Updated (Phase 2)
│       ├── categorical_judge.py
│       ├── goal_achievement_judge.py
│       ├── configs.py              # ✅ NEW: Unified config classes (Phase 2)
│       ├── shared_utils.py         # ✅ NEW: Phase 1
│       ├── mixins.py               # ✅ NEW: Phase 1 (consolidated)
│       ├── evaluation_patterns.py  # NEW: Phase 3
│       └── templates/
│           ├── prompt_metric.jinja
│           └── conversational_prompt_metric.jinja
```

---

## Appendix B: References

**Key Files Analyzed:**
- `sdk/metrics/base.py`
- `sdk/metrics/conversational/base.py`
- `sdk/metrics/providers/native/base.py`
- `sdk/metrics/providers/native/conversational_judge.py`
- `sdk/metrics/providers/native/numeric_judge.py`
- `sdk/metrics/providers/native/goal_achievement_judge.py`
- `sdk/metrics/providers/deepeval/metric_base.py`
- `sdk/metrics/providers/deepeval/conversational_base.py`

**Related Documents:**
- `penelope/MULTI_TURN_METRICS_DESIGN.md`
- SDK metrics documentation

---

**Document Status:** Ready for Review  
**Last Updated:** November 7, 2025  
**Author:** AI Assistant (Claude Sonnet 4.5)


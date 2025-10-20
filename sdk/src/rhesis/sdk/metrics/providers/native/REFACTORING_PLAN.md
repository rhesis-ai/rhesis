# Parameter Refactoring Plan: Native Metrics

**Goal**: Eliminate parameter duplication using Pydantic configs + dynamic getters/setters + auto-generated type hints

**Single Source of Truth**: Parameters defined ONCE in Pydantic config classes

---

## Phase 1: Convert Configs to Pydantic (2-3 hours)

### 1.1 Update Base Config
**File**: `sdk/src/rhesis/sdk/metrics/base.py`

**BEFORE (Dataclass):**
```python
from dataclasses import dataclass
from enum import Enum

@dataclass
class MetricConfig:
    class_name: Optional[str] = None
    backend: Optional[Union[str, Backend]] = Backend.RHESIS
    score_type: Optional[Union[str, ScoreType]] = None
    metric_type: Optional[Union[str, MetricType]] = None
    # ... other fields
    
    def __post_init__(self):
        # Manual enum conversion
        if isinstance(self.backend, str):
            self.backend = Backend(self.backend.lower())
        if isinstance(self.score_type, str):
            self.score_type = ScoreType(self.score_type.lower())
        # ... more conversions
```

**AFTER (Pydantic):**
```python
from pydantic import BaseModel, field_validator
from enum import Enum

class MetricConfig(BaseModel):
    class_name: Optional[str] = None
    backend: Union[str, Backend] = Backend.RHESIS
    score_type: Optional[Union[str, ScoreType]] = None
    metric_type: Optional[Union[str, MetricType]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    requires_ground_truth: bool = False
    requires_context: bool = False
    
    # Pydantic configuration
    model_config = {
        "validate_assignment": True,  # Validates on assignment too!
        "extra": "allow",  # Allow extra fields for extensibility
        "use_enum_values": False,  # Keep enums as enums
    }
    
    # Field validator - runs on single field
    @field_validator("backend", mode="before")
    @classmethod
    def validate_backend(cls, v):
        """Convert string to Backend enum"""
        if isinstance(v, str):
            return Backend(v.lower())
        return v
    
    @field_validator("score_type", mode="before")
    @classmethod
    def validate_score_type(cls, v):
        """Convert string to ScoreType enum"""
        if isinstance(v, str):
            return ScoreType(v.lower())
        return v
    
    @field_validator("metric_type", mode="before")
    @classmethod
    def validate_metric_type(cls, v):
        """Convert string to MetricType enum"""
        if isinstance(v, str):
            return MetricType(v.lower())
        return v
```

**Tasks:**
- [ ] Convert `MetricConfig` from `@dataclass` to Pydantic `BaseModel`
- [ ] Add `model_config` dictionary
- [ ] Add `@field_validator` for enum conversions
- [ ] Remove `__post_init__` method
- [ ] Test that enum conversion still works

---

### 1.2 Update PromptMetricConfig
**File**: `sdk/src/rhesis/sdk/metrics/providers/native/prompt_metric.py`

**BEFORE (Dataclass):**
```python
@dataclass
class PromptMetricConfig(MetricConfig):
    evaluation_prompt: Optional[str] = None
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    evaluation_examples: Optional[str] = None
    
    def __post_init__(self):
        return super().__post_init__()
```

**AFTER (Pydantic):**
```python
class PromptMetricConfig(MetricConfig):
    """Inherits from Pydantic MetricConfig - automatic validation!"""
    evaluation_prompt: Optional[str] = None
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    evaluation_examples: Optional[str] = None
    
    # No __post_init__ needed!
```

**Tasks:**
- [ ] Remove `@dataclass` decorator
- [ ] Remove `__post_init__` method
- [ ] Verify inheritance from Pydantic `MetricConfig` works

---

### 1.3 Update PromptMetricNumericConfig
**File**: `sdk/src/rhesis/sdk/metrics/providers/native/prompt_metric_numeric.py`

**BEFORE (Dataclass with manual validation):**
```python
@dataclass
class PromptMetricNumericConfig(PromptMetricConfig):
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    threshold: Optional[float] = None
    threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL
    
    def __post_init__(self):
        if isinstance(self.threshold_operator, str):
            self.threshold_operator = ThresholdOperator(self.threshold_operator)
        self._validate_score_range(self.min_score, self.max_score)
        self._set_score_parameters(self.min_score, self.max_score, self.threshold)
        super().__post_init__()
    
    def _validate_score_range(self, min_score, max_score):
        if min_score is not None and max_score is None:
            raise ValueError("Only min_score was set, please set max_score")
        # ... more validation
    
    def _set_score_parameters(self, min_score, max_score, threshold):
        self.min_score = min_score if min_score is not None else 0
        # ... more logic
```

**AFTER (Pydantic with validators):**
```python
class PromptMetricNumericConfig(PromptMetricConfig):
    min_score: float = 0.0
    max_score: float = 1.0
    threshold: Optional[float] = None
    threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL
    
    model_config = {
        "validate_assignment": True,  # Validates on every assignment!
    }
    
    # Field validator - converts string to enum
    @field_validator("threshold_operator", mode="before")
    @classmethod
    def validate_threshold_operator(cls, v):
        """Convert string to ThresholdOperator enum"""
        if isinstance(v, str):
            return ThresholdOperator(v)
        return v
    
    # Model validator - validates multiple fields together
    @model_validator(mode="after")
    def validate_score_range_and_threshold(self):
        """
        Validate relationships between min_score, max_score, and threshold.
        This runs AFTER all fields are set.
        """
        # Validate min < max
        if self.min_score >= self.max_score:
            raise ValueError(
                f"min_score ({self.min_score}) must be less than "
                f"max_score ({self.max_score})"
            )
        
        # Auto-calculate threshold if not provided
        if self.threshold is None:
            self.threshold = self.min_score + (self.max_score - self.min_score) / 2
        
        # Validate threshold is in range
        if not (self.min_score <= self.threshold <= self.max_score):
            raise ValueError(
                f"threshold ({self.threshold}) must be between "
                f"min_score ({self.min_score}) and max_score ({self.max_score})"
            )
        
        return self  # Must return self!
```

**Tasks:**
- [ ] Remove `@dataclass` decorator
- [ ] Remove `__post_init__`, `_validate_score_range()`, `_set_score_parameters()`
- [ ] Add `@field_validator` for `threshold_operator`
- [ ] Add `@model_validator` for score range and threshold validation
- [ ] Test validation with invalid values
- [ ] Test auto-calculation of threshold

---

### 1.4 Update PromptMetricCategoricalConfig
**File**: `sdk/src/rhesis/sdk/metrics/providers/native/prompt_metric_categorical.py`

**BEFORE (Dataclass with multiple validation methods):**
```python
@dataclass
class PromptMetricCategoricalConfig(PromptMetricConfig):
    categories: Optional[List[str]] = None
    passing_categories: Optional[Union[str, List[str]]] = None
    
    def __post_init__(self):
        self._validate_categories()
        self._validate_passing_categories()
        self._normalize_passing_categories()
        self._validate_passing_categories_subset()
    
    def _validate_categories(self):
        if not isinstance(self.categories, list) or len(self.categories) < 2:
            raise ValueError("categories must be a list with at least 2 items")
    
    def _validate_passing_categories(self):
        if not isinstance(self.passing_categories, (str, list)):
            raise ValueError("passing_categories must be a string or list")
    
    def _normalize_passing_categories(self):
        if isinstance(self.passing_categories, str):
            self.passing_categories = [self.passing_categories]
    
    def _validate_passing_categories_subset(self):
        if not set(self.passing_categories).issubset(set(self.categories)):
            raise ValueError("passing_categories must be subset of categories")
```

**AFTER (Pydantic with validators):**
```python
from pydantic import Field

class PromptMetricCategoricalConfig(PromptMetricConfig):
    # Use Field() for additional validation
    categories: List[str] = Field(min_length=2, description="List of valid categories")
    passing_categories: Union[str, List[str]] = Field(description="Categories considered passing")
    
    model_config = {
        "validate_assignment": True,
    }
    
    # Field validator - normalizes passing_categories to list
    @field_validator("passing_categories", mode="before")
    @classmethod
    def normalize_passing_categories(cls, v):
        """Convert single string to list"""
        if isinstance(v, str):
            return [v]
        if not isinstance(v, list):
            raise ValueError("passing_categories must be a string or list")
        return v
    
    # Model validator - validates relationship between fields
    @model_validator(mode="after")
    def validate_passing_categories_subset(self):
        """
        Validate that passing_categories is a subset of categories.
        This runs after both fields are set.
        """
        # Check passing_categories is subset
        if not set(self.passing_categories).issubset(set(self.categories)):
            missing = set(self.passing_categories) - set(self.categories)
            raise ValueError(
                f"passing_categories must be a subset of categories. "
                f"Missing categories: {missing}\n"
                f"Valid categories: {self.categories}\n"
                f"Provided passing_categories: {self.passing_categories}"
            )
        
        # Check not more passing than total
        if len(self.passing_categories) > len(self.categories):
            raise ValueError(
                f"Number of passing_categories ({len(self.passing_categories)}) "
                f"cannot exceed number of categories ({len(self.categories)})"
            )
        
        return self  # Must return self!
```

**Tasks:**
- [ ] Remove `@dataclass` decorator
- [ ] Remove all `_validate_*` methods and `__post_init__`
- [ ] Add `Field()` with `min_length=2` for categories
- [ ] Add `@field_validator` for normalizing `passing_categories`
- [ ] Add `@model_validator` for subset validation
- [ ] Test validation with invalid combinations

---

## Phase 2: Create Helper Utilities (30 min)

### 2.1 Create Decorator for Auto-Type-Hints
**File**: `sdk/src/rhesis/sdk/metrics/utils.py` (new file) or add to `base.py`

**Complete Implementation:**
```python
def mirror_config_fields(config_class):
    """
    Decorator that automatically generates type hints from a Pydantic config class.
    
    This eliminates the need to manually duplicate field definitions as type hints
    in metric classes. The decorator reads all fields from the Pydantic model and
    adds them as __annotations__ to the decorated class, enabling IDE autocomplete.
    
    Args:
        config_class: A Pydantic BaseModel subclass containing field definitions
        
    Returns:
        A decorator function that adds type hints to a class
        
    Example:
        ```python
        # Config defines fields once
        class MyConfig(BaseModel):
            name: str
            value: int = 0
        
        # Decorator auto-generates type hints
        @mirror_config_fields(MyConfig)
        class MyClass:
            def __init__(self, config: MyConfig):
                self.config = config
        
        # Now IDE knows about 'name' and 'value' attributes!
        obj = MyClass(MyConfig(name="test"))
        obj.name  # ← IDE autocompletes this!
        ```
    """
    def decorator(cls):
        # Initialize __annotations__ if it doesn't exist
        if not hasattr(cls, '__annotations__'):
            cls.__annotations__ = {}
        
        # Check if config_class is a Pydantic model (v2.x)
        if hasattr(config_class, 'model_fields'):
            # Iterate over all fields in the Pydantic model
            for field_name, field_info in config_class.model_fields.items():
                # Add the field's type annotation to the class
                # field_info.annotation contains the full type hint
                cls.__annotations__[field_name] = field_info.annotation
        
        return cls
    
    return decorator


# Optional: Enhanced version with logging for debugging
def mirror_config_fields_debug(config_class):
    """
    Enhanced version of mirror_config_fields with debug logging.
    Use during development to see which fields are being mirrored.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    def decorator(cls):
        if not hasattr(cls, '__annotations__'):
            cls.__annotations__ = {}
        
        if hasattr(config_class, 'model_fields'):
            logger.debug(f"Mirroring fields from {config_class.__name__} to {cls.__name__}")
            
            for field_name, field_info in config_class.model_fields.items():
                cls.__annotations__[field_name] = field_info.annotation
                logger.debug(f"  Added: {field_name}: {field_info.annotation}")
        
        return cls
    
    return decorator
```

**Usage Example:**
```python
from pydantic import BaseModel
from typing import Optional

# 1. Define config with fields
class PromptMetricNumericConfig(BaseModel):
    name: str
    min_score: float = 0.0
    max_score: float = 1.0
    threshold: Optional[float] = None

# 2. Apply decorator to metric class
@mirror_config_fields(PromptMetricNumericConfig)
class RhesisPromptMetricNumeric:
    def __init__(self, config: PromptMetricNumericConfig):
        self.config = config
    
    # No need to define type hints here!
    # They're auto-generated from config

# 3. IDE now knows about all config fields!
metric = RhesisPromptMetricNumeric(
    config=PromptMetricNumericConfig(name="test", min_score=0, max_score=10)
)

# These all work with autocomplete:
metric.name        # IDE suggests this!
metric.min_score   # IDE suggests this!
metric.max_score   # IDE suggests this!
metric.threshold   # IDE suggests this!
```

**Tasks:**
- [ ] Create `utils.py` file if it doesn't exist
- [ ] Add `mirror_config_fields` function
- [ ] Add comprehensive docstring
- [ ] Add usage example in docstring
- [ ] Test with a simple config/class combination
- [ ] Verify IDE autocomplete works after decoration

---

## Phase 3: Refactor Base Metric Class (1-2 hours)

### 3.1 Update RhesisPromptMetricBase
**File**: `sdk/src/rhesis/sdk/metrics/providers/native/prompt_metric.py`

**BEFORE (Manual field extraction):**
```python
class RhesisPromptMetricBase(BaseMetric):
    def __init__(self, config: PromptMetricConfig, model: Optional[Union[BaseLLM, str]] = None):
        self.config = config
        super().__init__(config=self.config, model=model)
        
        # Duplicate extraction - BAD!
        self.evaluation_prompt = self.config.evaluation_prompt
        self.evaluation_steps = self.config.evaluation_steps
        self.reasoning = self.config.reasoning
        self.evaluation_examples = self.config.evaluation_examples
    
    def to_dict(self) -> Dict[str, Any]:
        """Manual serialization"""
        from dataclasses import asdict
        return asdict(self.to_config())
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        """Manual deserialization"""
        from dataclasses import fields
        valid_fields = {field.name for field in fields(ConfigClass)}
        filtered = {k: v for k, v in config.items() if k in valid_fields}
        return cls.from_config(ConfigClass(**filtered))
```

**AFTER (Dynamic attribute access):**
```python
class RhesisPromptMetricBase(BaseMetric):
    """Base metric with dynamic config-backed attributes"""
    
    def __init__(self, config: PromptMetricConfig, model: Optional[Union[BaseLLM, str]] = None):
        # Use object.__setattr__ during init to avoid recursion
        object.__setattr__(self, 'config', config)
        object.__setattr__(self, 'model', self.set_model(model))
        
        # No field extraction needed!
        self._setup_jinja_environment()
    
    def __getattr__(self, name: str):
        """
        Automatically delegate attribute access to config.
        
        This allows: metric.min_score → metric.config.min_score
        Without manual property definitions!
        
        Args:
            name: Attribute name to get
            
        Returns:
            Value from config if it exists there
            
        Raises:
            AttributeError: If attribute doesn't exist in config
        """
        # Prevent infinite recursion for special attributes
        if name in ('config', 'model'):
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            )
        
        # Try to get from config
        if hasattr(self, 'config') and hasattr(self.config, name):
            return getattr(self.config, name)
        
        # Attribute not found
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )
    
    def __setattr__(self, name: str, value: Any):
        """
        Automatically delegate attribute assignment to config with validation.
        
        This allows: metric.min_score = 5 → metric.config.min_score = 5
        Pydantic validates the assignment automatically!
        
        Args:
            name: Attribute name to set
            value: New value
        """
        # Special attributes that go on the instance, not config
        _instance_attrs = ('config', 'model', '_jinja_env', '_template_service')
        
        if name in _instance_attrs:
            # Set directly on instance
            object.__setattr__(self, name, value)
            return
        
        # If config exists and has this field, update config
        if hasattr(self, 'config') and hasattr(self.config, name):
            # This triggers Pydantic validation!
            setattr(self.config, name, value)
        else:
            # Field not in config, set on instance
            object.__setattr__(self, name, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary using Pydantic.
        One line instead of manual conversion!
        """
        return self.config.model_dump(exclude_none=True)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """
        Deserialize from dictionary using Pydantic.
        Automatic validation + no manual field filtering!
        """
        # Get the config class for this metric type
        config_class = cls._get_config_class()
        
        # Pydantic validates and converts automatically
        config = config_class.model_validate(data)
        
        return cls(config=config)
    
    def push(self) -> None:
        """
        Push to backend using Pydantic serialization.
        mode='json' ensures proper enum serialization.
        """
        client = Client()
        
        # Pydantic handles enum conversion, None exclusion, etc.
        config_dict = self.config.model_dump(mode='json', exclude_none=True)
        config_dict = sdk_config_to_backend_config(config_dict)
        
        client.send_request(Endpoints.METRICS, Methods.POST, config_dict)
    
    @classmethod
    def pull(cls, name: Optional[str] = None, nano_id: Optional[str] = None):
        """Pull from backend with automatic Pydantic validation"""
        if not name and not nano_id:
            raise ValueError("Either name or nano_id must be provided")
        
        client = Client()
        filter_field = "nano_id" if nano_id else "name"
        filter_value = nano_id or name
        
        configs = client.send_request(
            Endpoints.METRICS,
            Methods.GET,
            params={"$filter": f"{filter_field} eq '{filter_value}'"},
        )
        
        if not configs:
            raise ValueError(f"No metric found with {filter_field} {filter_value}")
        if len(configs) > 1:
            raise ValueError(f"Multiple metrics found, use nano_id")
        
        config_data = backend_config_to_sdk_config(configs[0])
        
        # Pydantic validates automatically!
        return cls.from_dict(config_data)
    
    @classmethod
    @abstractmethod
    def _get_config_class(cls):
        """
        Return the config class for this metric type.
        Must be implemented by subclasses.
        """
        pass
```

**Tasks:**
- [ ] Remove manual field extraction in `__init__`
- [ ] Use `object.__setattr__` during init to avoid recursion
- [ ] Add `__getattr__` method with proper error handling
- [ ] Add `__setattr__` method with config delegation
- [ ] Update `to_dict()` to use `config.model_dump()`
- [ ] Update `from_dict()` to use `config.model_validate()`
- [ ] Update `push()` to use `config.model_dump(mode='json')`
- [ ] Update `pull()` to use Pydantic validation
- [ ] Add `_get_config_class()` abstract method
- [ ] Test attribute access and assignment
- [ ] Verify validation happens on assignment

---

## Phase 4: Refactor Metric Classes (1-2 hours)

### 4.1 Update RhesisPromptMetricNumeric
**File**: `sdk/src/rhesis/sdk/metrics/providers/native/prompt_metric_numeric.py`

**BEFORE (Long parameter list + manual extraction):**
```python
class RhesisPromptMetricNumeric(RhesisPromptMetricBase):
    def __init__(
        self,
        evaluation_prompt: str,
        evaluation_steps: Optional[str] = None,
        reasoning: Optional[str] = None,
        evaluation_examples: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        threshold: Optional[float] = None,
        threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metric_type: Optional[Union[str, MetricType]] = None,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs,
    ):
        # Create config by repeating ALL parameters
        self.config = PromptMetricNumericConfig(
            evaluation_prompt=evaluation_prompt,
            evaluation_steps=evaluation_steps,
            reasoning=reasoning,
            evaluation_examples=evaluation_examples,
            min_score=min_score,
            max_score=max_score,
            threshold=threshold,
            threshold_operator=threshold_operator,
            name=name,
            description=description,
            metric_type=metric_type,
            score_type=SCORE_TYPE,
            class_name=self.__class__.__name__,
        )
        super().__init__(config=self.config, model=model)
        
        # Manual extraction - duplication!
        self.min_score = self.config.min_score
        self.max_score = self.config.max_score
        self.threshold = self.config.threshold
        self.threshold_operator = self.config.threshold_operator
        
        self._setup_jinja_environment()
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        # Manual field filtering
        valid_fields = {field.name for field in fields(PromptMetricNumericConfig)}
        filtered_config = {k: v for k, v in config.items() if k in valid_fields}
        return cls.from_config(PromptMetricNumericConfig(**filtered_config))
```

**AFTER (Clean with decorator + **kwargs):**
```python
from rhesis.sdk.metrics.utils import mirror_config_fields

@mirror_config_fields(PromptMetricNumericConfig)  # ← Auto-generates type hints!
class RhesisPromptMetricNumeric(RhesisPromptMetricBase):
    """
    Numeric metric with automatic parameter handling.
    
    All config fields are accessible via attributes (e.g., metric.min_score)
    thanks to __getattr__ in base class and auto-generated type hints from decorator.
    """
    
    def __init__(
        self,
        config: Optional[PromptMetricNumericConfig] = None,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs,  # ← Accept any parameters from config
    ):
        """
        Initialize numeric metric.
        
        You can either:
        1. Pass a config object: RhesisPromptMetricNumeric(config=my_config)
        2. Pass parameters as kwargs: RhesisPromptMetricNumeric(name="test", min_score=0, ...)
        
        Args:
            config: Pre-built config object (if provided, kwargs are ignored)
            model: LLM model to use
            **kwargs: Any field from PromptMetricNumericConfig
                     (name, evaluation_prompt, min_score, max_score, etc.)
        
        Example:
            ```python
            # Option 1: Pass parameters
            metric = RhesisPromptMetricNumeric(
                name="accuracy",
                evaluation_prompt="Rate accuracy",
                min_score=0,
                max_score=10,
                threshold=7,
            )
            
            # Option 2: Pass config
            config = PromptMetricNumericConfig(name="accuracy", ...)
            metric = RhesisPromptMetricNumeric(config=config)
            
            # Access fields - IDE autocompletes these!
            print(metric.min_score)  # 0
            metric.threshold = 8     # Updates with validation
            ```
        """
        if config is None:
            # Create config from kwargs - Pydantic validates!
            config = PromptMetricNumericConfig(
                class_name=self.__class__.__name__,
                score_type=ScoreType.NUMERIC,
                **kwargs,  # All parameters come from kwargs
            )
        
        # Initialize base with config - that's it!
        super().__init__(config=config, model=model)
        
        # No field extraction!
        # Access via: self.min_score → self.config.min_score (automatic)
    
    @classmethod
    def _get_config_class(cls):
        """Tell base class which config type to use"""
        return PromptMetricNumericConfig
    
    # That's it! No more code needed!
    # All fields accessible via __getattr__ from base class
    # Type hints auto-generated by decorator
    # Can use: self.min_score, self.max_score, etc. everywhere
```

**Usage Example:**
```python
# Create metric - clean API
metric = RhesisPromptMetricNumeric(
    name="accuracy",
    evaluation_prompt="Rate the accuracy",
    min_score=0,
    max_score=10,
    threshold=7,
)

# Read - works automatically, IDE autocompletes
print(metric.min_score)       # 0
print(metric.max_score)       # 10
print(metric.threshold)       # 7
print(metric.name)            # "accuracy"

# Write - validates automatically
metric.min_score = 2          # ✅ Works, updates config
metric.threshold = 8           # ✅ Works, updates config

# Validation catches errors
try:
    metric.min_score = 15      # ❌ Error: min_score must be < max_score
except ValueError as e:
    print(f"Validation error: {e}")

# Serialization - one line
data = metric.to_dict()

# Push/pull - just works
metric.push()
loaded = RhesisPromptMetricNumeric.pull(name="accuracy")
```

**Tasks:**
- [ ] Add import: `from rhesis.sdk.metrics.utils import mirror_config_fields`
- [ ] Add `@mirror_config_fields(PromptMetricNumericConfig)` decorator
- [ ] Simplify `__init__` to accept `config=None, model=None, **kwargs`
- [ ] Remove all manual parameter passing to config (use `**kwargs`)
- [ ] Remove lines 160-163 (field extraction)
- [ ] Add `_get_config_class()` classmethod
- [ ] Remove old `from_dict()` implementation (use inherited one)
- [ ] Test that all parameters work
- [ ] Verify IDE autocomplete works
- [ ] Test validation on assignment

---

### 4.2 Update RhesisPromptMetricCategorical
**File**: `sdk/src/rhesis/sdk/metrics/providers/native/prompt_metric_categorical.py`

**BEFORE:**
```python
class RhesisPromptMetricCategorical(RhesisPromptMetricBase):
    def __init__(
        self,
        categories: Optional[List[str]] = None,
        passing_categories: Optional[Union[str, List[str]]] = None,
        evaluation_steps: Optional[str] = None,
        # ... 10+ more parameters
    ):
        self.config = PromptMetricCategoricalConfig(
            categories=categories,
            passing_categories=passing_categories,
            # ... repeat all parameters
        )
        super().__init__(config=self.config, model=model)
        
        # Manual extraction
        self.categories = self.config.categories
        self.passing_categories = self.config.passing_categories
```

**AFTER:**
```python
from rhesis.sdk.metrics.utils import mirror_config_fields

@mirror_config_fields(PromptMetricCategoricalConfig)
class RhesisPromptMetricCategorical(RhesisPromptMetricBase):
    """Categorical metric with automatic parameter handling"""
    
    def __init__(
        self,
        config: Optional[PromptMetricCategoricalConfig] = None,
        model: Optional[Union[BaseLLM, str]] = None,
        **kwargs,
    ):
        """
        Initialize categorical metric.
        
        Example:
            ```python
            metric = RhesisPromptMetricCategorical(
                name="sentiment",
                evaluation_prompt="Classify sentiment",
                categories=["positive", "neutral", "negative"],
                passing_categories=["positive"],  # or just "positive"
            )
            
            # Access fields - autocomplete works!
            print(metric.categories)          # ["positive", "neutral", "negative"]
            print(metric.passing_categories)  # ["positive"]
            
            # Modify with validation
            metric.passing_categories = ["positive", "neutral"]  # ✅ Valid
            ```
        """
        if config is None:
            config = PromptMetricCategoricalConfig(
                class_name=self.__class__.__name__,
                score_type=ScoreType.CATEGORICAL,
                metric_type=MetricType.RAG,
                **kwargs,
            )
        
        super().__init__(config=config, model=model)
    
    @classmethod
    def _get_config_class(cls):
        return PromptMetricCategoricalConfig
```

**Tasks:**
- [ ] Add `@mirror_config_fields(PromptMetricCategoricalConfig)` decorator
- [ ] Simplify `__init__` to `config=None, model=None, **kwargs`
- [ ] Remove manual parameter passing (use `**kwargs`)
- [ ] Remove manual field extraction (lines 149-150)
- [ ] Add `_get_config_class()` classmethod
- [ ] Test categorical validation
- [ ] Verify passing_categories normalization still works

---

## Phase 5: Simplify Factory (30 min)

### 5.1 Update RhesisMetricFactory
**File**: `sdk/src/rhesis/sdk/metrics/providers/native/factory.py`

**BEFORE (Manual parameter tracking - 115 lines!):**
```python
class RhesisMetricFactory(BaseMetricFactory):
    _metrics = {
        "RhesisPromptMetricCategorical": RhesisPromptMetricCategorical,
        "RhesisPromptMetricNumeric": RhesisPromptMetricNumeric,
    }
    
    # Define which parameters each metric class accepts - MANUAL MAINTENANCE!
    _supported_params = {
        "RhesisPromptMetricNumeric": {
            "threshold",
            "reference_score",
            "threshold_operator",
            "score_type",
            "evaluation_prompt",
            "evaluation_steps",
            "reasoning",
            "evaluation_examples",
            "min_score",
            "max_score",
            "provider",
            "model",
            "api_key",
            "metric_type",
            "name",
            # If you add a parameter, must update this list!
        },
        "RhesisDetailedPromptMetricNumeric": {
            # ... another 15 parameters
        },
    }
    
    # Define required parameters - MORE MANUAL MAINTENANCE!
    _required_params = {
        "RhesisPromptMetricNumeric": {"name", "evaluation_prompt", "evaluation_steps", "reasoning"}
    }
    
    def create(self, class_name: str, **kwargs) -> BaseMetric:
        if class_name not in self._metrics:
            available_classes = list(self._metrics.keys())
            raise ValueError(
                f"Unknown metric class: {class_name}. Available classes: {available_classes}"
            )
        
        # Extract parameters from the 'parameters' dictionary if present
        parameters = (
            kwargs.pop("parameters", {}) if isinstance(kwargs.get("parameters"), dict) else {}
        )
        
        # Combine parameters with kwargs, with kwargs taking precedence
        combined_kwargs = {**parameters, **kwargs}
        
        # Set the name parameter if not present
        if "name" not in combined_kwargs and class_name in self._metrics:
            combined_kwargs["name"] = class_name.lower()
        
        # Check for required parameters - MANUAL VALIDATION
        required_params = self._required_params.get(class_name, set())
        missing_params = required_params - set(combined_kwargs.keys())
        if missing_params:
            raise ValueError(
                f"Missing required parameters for {class_name}: {missing_params}. "
                f"Provided parameters: {set(combined_kwargs.keys())}"
            )
        
        # Filter kwargs to only include supported parameters - MANUAL FILTERING
        supported_params = self._supported_params.get(class_name, set())
        filtered_kwargs = {k: v for k, v in combined_kwargs.items() if k in supported_params}
        
        return self._metrics[class_name](**filtered_kwargs)
    
    def list_supported_metrics(self) -> List[str]:
        return list(self._metrics.keys())
```

**AFTER (Pydantic handles everything - 25 lines!):**
```python
class RhesisMetricFactory(BaseMetricFactory):
    """
    Simplified factory - no parameter lists needed!
    Pydantic handles all validation and parameter checking.
    """
    
    _metrics = {
        "RhesisPromptMetricCategorical": RhesisPromptMetricCategorical,
        "RhesisPromptMetricNumeric": RhesisPromptMetricNumeric,
    }
    
    # No _supported_params dictionary needed!
    # No _required_params dictionary needed!
    # Pydantic configs define and validate everything!
    
    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """
        Create a metric instance. Pydantic validates parameters automatically.
        
        Args:
            class_name: The metric class name (e.g., 'RhesisPromptMetricNumeric')
            **kwargs: Any parameters for the metric (validated by Pydantic)
        
        Returns:
            BaseMetric: The created metric instance
        
        Raises:
            ValueError: If class_name is unknown
            ValidationError: If parameters are invalid (from Pydantic)
        
        Example:
            ```python
            factory = RhesisMetricFactory()
            
            # Create metric - Pydantic validates automatically!
            metric = factory.create(
                "RhesisPromptMetricNumeric",
                name="accuracy",
                evaluation_prompt="Rate accuracy",
                min_score=0,
                max_score=10,
            )
            
            # Invalid parameters? Pydantic gives helpful error
            try:
                metric = factory.create(
                    "RhesisPromptMetricNumeric",
                    min_score=10,
                    max_score=5,  # Error: min must be < max
                )
            except Exception as e:
                print(f"Validation error: {e}")
            ```
        """
        # Check if class exists
        if class_name not in self._metrics:
            available_classes = list(self._metrics.keys())
            raise ValueError(
                f"Unknown metric class: {class_name}. "
                f"Available classes: {available_classes}"
            )
        
        metric_class = self._metrics[class_name]
        
        try:
            # Just call the class - Pydantic validates everything!
            # No parameter filtering, no required param checking needed
            return metric_class(**kwargs)
        
        except Exception as e:
            # Pydantic gives detailed validation errors
            raise ValueError(
                f"Failed to create {class_name}. "
                f"Validation error: {e}"
            ) from e
    
    def list_supported_metrics(self) -> List[str]:
        """List available metric class names"""
        return list(self._metrics.keys())
```

**Comparison:**
```
BEFORE: 115 lines with manual parameter tracking
AFTER:  25 lines with automatic validation

Lines of code saved: 90 lines (78% reduction!)
Maintenance: No need to update parameter lists when adding fields!
Validation: Better error messages from Pydantic
```

**Tasks:**
- [ ] Remove `_supported_params` dictionary (lines 21-58)
- [ ] Remove `_required_params` dictionary (lines 61-63)
- [ ] Simplify `create()` method - remove parameter extraction logic
- [ ] Remove manual parameter filtering logic
- [ ] Remove manual required parameter checking
- [ ] Wrap metric creation in try/except
- [ ] Test creating metrics with valid parameters
- [ ] Test creating metrics with invalid parameters (verify Pydantic errors)
- [ ] Test that helpful error messages are shown

---

## Phase 6: Update Tests (1-2 hours)

### 6.1 Update Config Tests
**Files**: `tests/sdk/metrics/providers/native/test_prompt_metric*.py`

- [ ] Update config creation to use Pydantic syntax
- [ ] Test validation errors (Pydantic gives different error messages)
- [ ] Test `model_dump()` instead of `asdict()`
- [ ] Test `model_validate()` for deserialization

### 6.2 Update Metric Tests
- [ ] Verify attribute access works via `__getattr__`
- [ ] Test attribute mutation with validation
- [ ] Test `to_dict()` / `from_dict()` with Pydantic
- [ ] Test `push()` / `pull()` still work

---

## Phase 7: Update Documentation (30 min)

- [ ] Update README with new parameter handling approach
- [ ] Add examples showing simplified usage
- [ ] Document that parameters are validated by Pydantic
- [ ] Add note about `validate_assignment=True` behavior

---

## Migration Checklist

### Before Starting
- [ ] Create feature branch: `git checkout -b refactor/pydantic-parameters`
- [ ] Run existing tests: ensure all pass
- [ ] Install Pydantic: `pip install pydantic>=2.0`

### During Refactoring
- [ ] Make changes incrementally (one phase at a time)
- [ ] Run tests after each phase
- [ ] Commit after each successful phase

### After Completion
- [ ] All tests passing
- [ ] Manual testing of `push()` / `pull()`
- [ ] IDE autocomplete verified
- [ ] Documentation updated
- [ ] Code review

---

## Expected Benefits

✅ **Single Source of Truth**: Parameters defined once in config  
✅ **No Duplication**: No manual getter/setter code  
✅ **Auto-Validation**: Pydantic validates on creation and assignment  
✅ **IDE Support**: Auto-generated type hints for autocomplete  
✅ **Simpler Factory**: No hardcoded parameter lists  
✅ **Better Errors**: Pydantic gives detailed validation messages  
✅ **Easier Maintenance**: Add parameter once, works everywhere  

---

## Rollback Plan

If issues arise:
1. Revert to previous commit: `git reset --hard <commit>`
2. Cherry-pick successful phases if needed
3. Keep Pydantic configs but revert dynamic attribute access

---

## Estimated Time

- **Phase 1-2**: 3 hours
- **Phase 3-4**: 3 hours  
- **Phase 5-6**: 2 hours
- **Phase 7**: 30 min
- **Total**: ~8-9 hours

---

## Success Criteria

- [ ] All existing tests pass
- [ ] No parameter duplication in code
- [ ] IDE autocomplete works for all config fields
- [ ] Validation happens automatically on assignment
- [ ] `push()` and `pull()` methods work correctly
- [ ] Factory doesn't need parameter lists
- [ ] Can add new parameter by only editing config class

---

## Complete Usage Example

**After refactoring, here's how clean everything becomes:**

```python
# =============================================================================
# 1. Define parameters ONCE in config - single source of truth!
# =============================================================================
from pydantic import BaseModel, field_validator, model_validator

class PromptMetricNumericConfig(BaseModel):
    name: str
    evaluation_prompt: str
    min_score: float = 0.0
    max_score: float = 1.0
    threshold: Optional[float] = None
    
    model_config = {"validate_assignment": True}
    
    @model_validator(mode="after")
    def validate_and_set_threshold(self):
        if self.min_score >= self.max_score:
            raise ValueError("min_score must be < max_score")
        if self.threshold is None:
            self.threshold = (self.min_score + self.max_score) / 2
        return self


# =============================================================================
# 2. Metric class is TINY - decorator auto-generates type hints
# =============================================================================
from rhesis.sdk.metrics.utils import mirror_config_fields

@mirror_config_fields(PromptMetricNumericConfig)
class RhesisPromptMetricNumeric(RhesisPromptMetricBase):
    def __init__(self, config=None, model=None, **kwargs):
        if config is None:
            config = PromptMetricNumericConfig(
                class_name=self.__class__.__name__,
                score_type=ScoreType.NUMERIC,
                **kwargs
            )
        super().__init__(config=config, model=model)
    
    @classmethod
    def _get_config_class(cls):
        return PromptMetricNumericConfig
    
    # That's it! Only ~10 lines of code!


# =============================================================================
# 3. Using the metric - clean, validated, autocompleted
# =============================================================================

# Create metric
metric = RhesisPromptMetricNumeric(
    name="accuracy",
    evaluation_prompt="Rate the accuracy from 0 to 10",
    min_score=0,
    max_score=10,
    threshold=7,
)

# ✅ IDE autocompletes these (from decorator)
print(metric.name)        # "accuracy"
print(metric.min_score)   # 0
print(metric.max_score)   # 10
print(metric.threshold)   # 7

# ✅ Can modify with automatic validation
metric.threshold = 8      # Works!
metric.min_score = 2      # Works!

try:
    metric.min_score = 15  # ❌ Pydantic validates: must be < max_score!
except ValueError as e:
    print(f"Caught validation error: {e}")

# ✅ Serialization is one line
data = metric.to_dict()
print(data)  # {'name': 'accuracy', 'min_score': 2, 'max_score': 10, ...}

# ✅ Deserialization is one line
loaded = RhesisPromptMetricNumeric.from_dict(data)

# ✅ Push/pull work seamlessly
metric.push()
pulled = RhesisPromptMetricNumeric.pull(name="accuracy")

# ✅ Factory is simple
factory = RhesisMetricFactory()
metric2 = factory.create(
    "RhesisPromptMetricNumeric",
    name="test",
    evaluation_prompt="Test",
    min_score=0,
    max_score=100,
)


# =============================================================================
# 4. Adding a new parameter? Edit ONE place!
# =============================================================================

# Add to config
class PromptMetricNumericConfig(BaseModel):
    name: str
    evaluation_prompt: str
    min_score: float = 0.0
    max_score: float = 1.0
    threshold: Optional[float] = None
    new_field: str = "default"  # ← Just add this!

# That's it! Now:
# - metric.new_field works (via __getattr__)
# - IDE autocompletes it (via decorator)
# - Validation happens (via Pydantic)
# - Serialization includes it (via model_dump)
# - Factory accepts it (via **kwargs)
# - No other code changes needed!
```

---

## Before vs After Summary

### Parameter Count
| Aspect | Before | After | Improvement |
|--------|--------|-------|-------------|
| Define parameters | Config + `__init__` + extraction | Config only | **3x → 1x** |
| Type hints | Manual | Auto-generated | **0 code** |
| Validation | Manual methods | Pydantic validators | **Cleaner** |
| Serialization | Manual | `model_dump()` | **1 line** |
| Factory params | Hardcoded sets | None needed | **-90 lines** |

### Lines of Code
| Component | Before | After | Saved |
|-----------|--------|-------|-------|
| Config validation | ~30 lines | ~15 lines | 50% |
| Metric `__init__` | ~25 lines | ~10 lines | 60% |
| Metric properties | ~40 lines | 0 lines | 100% |
| Factory | ~115 lines | ~25 lines | 78% |
| **Total** | **~210 lines** | **~50 lines** | **76%** |

### Maintenance
- **Adding a parameter**: 1 place (config) instead of 5+ places
- **Validation**: Automatic via Pydantic
- **IDE support**: Automatic via decorator
- **Serialization**: Automatic via Pydantic

🎉 **Result**: Cleaner, shorter, more maintainable code with better validation and IDE support!


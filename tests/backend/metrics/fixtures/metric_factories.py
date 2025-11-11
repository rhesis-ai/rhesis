"""
📊 Metric Data Factories

Factories for generating consistent test data for metrics-related entities.
These factories follow the established pattern from data_factories.py
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from faker import Faker

fake = Faker()
Faker.seed(12345)


@dataclass
class MetricConfigFactory:
    """Factory for generating metric configuration dictionaries (not DB models)."""
    
    @classmethod
    def numeric_config(cls,  **overrides) -> Dict[str, Any]:
        """Generate numeric metric configuration."""
        config = {
            "name": "Numeric Quality Metric",
            "class_name": "RhesisPromptMetric",
            "backend": "rhesis",
            "description": "Evaluates quality on a numeric scale",
            "parameters": {
                "evaluation_prompt": "Rate the quality of this response from 0 to 10",
                "evaluation_steps": "1. Check accuracy\n2. Check completeness\n3. Rate overall",
                "reasoning": "Quality assessment is important for response evaluation",
                "score_type": "numeric",
                "min_score": 0,
                "max_score": 10,
                "threshold": 7,
                "threshold_operator": ">=",
            }
        }
        config.update(overrides)
        return config
    
    @classmethod
    def categorical_config(cls, **overrides) -> Dict[str, Any]:
        """Generate categorical metric configuration."""
        config = {
            "name": "Sentiment Metric",
            "class_name": "RhesisPromptMetric",
            "backend": "rhesis",
            "description": "Classifies sentiment of response",
            "parameters": {
                "evaluation_prompt": "Classify the sentiment of this response",
                "evaluation_steps": "1. Read the response\n2. Identify tone\n3. Classify sentiment",
                "reasoning": "Sentiment analysis for response quality",
                "score_type": "categorical",
                "reference_score": "positive",
            }
        }
        config.update(overrides)
        return config
    
    @classmethod
    def binary_config(cls, **overrides) -> Dict[str, Any]:
        """
        DEPRECATED: Binary metrics have been migrated to categorical.
        This method now returns a categorical metric configuration.
        """
        config = {
            "name": "Pass/Fail Metric",
            "class_name": "CategoricalJudge",
            "backend": "rhesis",
            "description": "Categorical pass/fail evaluation",
            "parameters": {
                "evaluation_prompt": "Does this response meet the criteria? Answer Pass or Fail",
                "evaluation_steps": "1. Check criteria\n2. Determine pass/fail",
                "reasoning": "Categorical evaluation for clear pass/fail criteria",
                "score_type": "categorical",
                "categories": ["Pass", "Fail"],
                "passing_categories": ["Pass"],
            }
        }
        config.update(overrides)
        return config
    
    @classmethod
    def with_model(cls, model_id: str, **overrides) -> Dict[str, Any]:
        """Generate metric configuration with custom model."""
        config = cls.numeric_config()
        config["model_id"] = model_id
        config.update(overrides)
        return config
    
    @classmethod
    def batch_configs(cls, count: int, variation: bool = True) -> List[Dict[str, Any]]:
        """Generate batch of metric configurations."""
        configs = []
        # Note: binary_config now returns categorical for backward compatibility
        types = [cls.numeric_config, cls.categorical_config, cls.binary_config]
        
        for i in range(count):
            if variation:
                config_func = types[i % len(types)]
                config = config_func()
                config["name"] = f"{config['name']} {i+1}"
            else:
                config = cls.numeric_config()
                config["name"] = f"Metric {i+1}"
            configs.append(config)
        
        return configs


@dataclass
class RhesisMetricConfigFactory:
    """Factory specifically for Rhesis native metrics."""
    
    @classmethod
    def prompt_metric_numeric(cls, **overrides) -> Dict[str, Any]:
        """Create RhesisPromptMetric with numeric score_type."""
        return MetricConfigFactory.numeric_config(**overrides)
    
    @classmethod
    def prompt_metric_categorical(cls, **overrides) -> Dict[str, Any]:
        """Create RhesisPromptMetric with categorical score_type."""
        return MetricConfigFactory.categorical_config(**overrides)
    
    @classmethod
    def prompt_metric_binary(cls, **overrides) -> Dict[str, Any]:
        """
        DEPRECATED: Create CategoricalJudge metric (formerly binary).
        Binary metrics have been migrated to categorical.
        """
        return MetricConfigFactory.binary_config(**overrides)
    
    @classmethod
    def with_all_optional_params(cls) -> Dict[str, Any]:
        """Create metric config with all optional parameters."""
        return {
            "name": "Comprehensive Quality Metric",
            "class_name": "RhesisPromptMetric",
            "backend": "rhesis",
            "description": "Comprehensive quality evaluation with all parameters",
            "parameters": {
                "evaluation_prompt": "Evaluate response quality comprehensively",
                "evaluation_steps": "1. Accuracy\n2. Completeness\n3. Clarity\n4. Relevance",
                "reasoning": "Comprehensive evaluation across multiple dimensions",
                "score_type": "numeric",
                "min_score": 0,
                "max_score": 100,
                "threshold": 70,
                "threshold_operator": ">=",
                "ground_truth_required": True,
                "context_required": True,
                "evaluation_examples": "Example 1: High quality response\nExample 2: Low quality response",
                "explanation": "Detailed explanation of scoring criteria",
            }
        }


@dataclass  
class RagasMetricConfigFactory:
    """Factory for Ragas framework metrics."""
    
    @classmethod
    def answer_relevancy(cls, threshold: float = 0.7, **overrides) -> Dict[str, Any]:
        """Create RagasAnswerRelevancy metric configuration."""
        config = {
            "name": "Ragas Answer Relevancy",
            "class_name": "RagasAnswerRelevancy",
            "backend": "ragas",
            "description": "Ragas answer relevancy metric",
            "parameters": {
                "threshold": threshold,
            }
        }
        config.update(overrides)
        return config
    
    @classmethod
    def contextual_precision(cls, threshold: float = 0.7, **overrides) -> Dict[str, Any]:
        """Create RagasContextualPrecision metric configuration."""
        config = {
            "name": "Ragas Contextual Precision",
            "class_name": "RagasContextualPrecision",
            "backend": "ragas",
            "description": "Ragas contextual precision metric",
            "parameters": {
                "threshold": threshold,
            }
        }
        config.update(overrides)
        return config


@dataclass
class DeepEvalMetricConfigFactory:
    """Factory for DeepEval framework metrics (currently commented out in backend)."""
    
    @classmethod
    def contextual_relevancy(cls, threshold: float = 0.7, **overrides) -> Dict[str, Any]:
        """Create DeepEvalContextualRelevancy metric configuration."""
        config = {
            "name": "DeepEval Contextual Relevancy",
            "class_name": "DeepEvalContextualRelevancy",
            "backend": "deepeval",
            "description": "DeepEval contextual relevancy metric",
            "parameters": {
                "threshold": threshold,
            }
        }
        config.update(overrides)
        return config


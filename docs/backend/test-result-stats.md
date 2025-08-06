# Test Result Statistics API

This guide covers the comprehensive test result statistics endpoint, designed for analytics dashboards and performance monitoring. The endpoint provides configurable data modes and extensive filtering capabilities for optimal performance.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Data Modes](#data-modes)
4. [Filtering System](#filtering-system)
5. [Multiple Value Support](#multiple-value-support)
6. [Response Structure](#response-structure)
7. [Performance Optimization](#performance-optimization)
8. [Complete Examples](#complete-examples)
9. [Best Practices](#best-practices)

## Overview

The test result statistics endpoint (`/test_results/stats`) provides powerful analytics capabilities for test performance analysis. It analyzes `test_metrics` JSONB data to determine pass/fail status per metric and overall test results.

### Key Features

- **Configurable Data Modes**: Retrieve only the data you need
- **Comprehensive Filtering**: Filter by any combination of test attributes  
- **Multiple Value Support**: Query multiple entities simultaneously
- **Performance Optimized**: Reduce payload size and response times
- **React Chart Ready**: Structured data for charting libraries

### Authentication

All requests require Bearer token authentication:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" "URL"
```

## Quick Start

### Basic Usage

```bash
# Get complete statistics for last 6 months
curl 'http://localhost:8080/test_results/stats' -H 'Authorization: Bearer YOUR_TOKEN'

# Get lightweight summary
curl 'http://localhost:8080/test_results/stats?mode=summary' -H 'Authorization: Bearer YOUR_TOKEN'

# Get metrics analysis only
curl 'http://localhost:8080/test_results/stats?mode=metrics' -H 'Authorization: Bearer YOUR_TOKEN'
```

### Basic Filtering

```bash
# Filter by specific test run
curl 'http://localhost:8080/test_results/stats?test_run_id=UUID' -H 'Authorization: Bearer YOUR_TOKEN'

# Filter by priority level
curl 'http://localhost:8080/test_results/stats?priority_min=3' -H 'Authorization: Bearer YOUR_TOKEN'

# Filter by date range
curl 'http://localhost:8080/test_results/stats?start_date=2024-01-01&end_date=2024-12-31' -H 'Authorization: Bearer YOUR_TOKEN'
```

## Data Modes

The endpoint supports configurable data modes for performance optimization:

### Performance-Optimized Modes

| Mode | Data Size | Response Time | Use Case |
|------|-----------|---------------|----------|
| `summary` | ~5% | ~50ms | Dashboard widgets, KPI tracking |
| `metrics` | ~20% | ~100ms | Metric-focused charts |
| `behavior` | ~15% | ~100ms | Behavior performance analysis |
| `category` | ~15% | ~100ms | Category comparison |
| `topic` | ~15% | ~100ms | Topic performance insights |
| `overall` | ~10% | ~75ms | Executive dashboards |
| `timeline` | ~40% | ~150ms | Trend analysis |
| `test_runs` | ~30% | ~125ms | Test run comparison |
| `all` | 100% | ~200-500ms | Comprehensive analytics |

### Mode Examples

**Summary Mode (Ultra-lightweight)**
```bash
curl 'http://localhost:8080/test_results/stats?mode=summary' -H 'Authorization: Bearer YOUR_TOKEN'
```

Returns only:
- `overall_pass_rates`
- `metadata`

**Metrics Mode (Individual metric analysis)**
```bash
curl 'http://localhost:8080/test_results/stats?mode=metrics&months=12' -H 'Authorization: Bearer YOUR_TOKEN'
```

Returns only:
- `metric_pass_rates` (Answer Fluency, Answer Relevancy, etc.)
- `metadata`

**Timeline Mode (Trend analysis)**
```bash
curl 'http://localhost:8080/test_results/stats?mode=timeline&months=6' -H 'Authorization: Bearer YOUR_TOKEN'
```

Returns only:
- `timeline` (monthly pass/fail trends)
- `metadata`

## Filtering System

The endpoint supports comprehensive filtering across multiple dimensions:

### Test-Level Filters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `test_set_ids` | UUID[] | Filter by test sets | `?test_set_ids=uuid1&test_set_ids=uuid2` |
| `behavior_ids` | UUID[] | Filter by behaviors | `?behavior_ids=uuid1&behavior_ids=uuid2` |
| `category_ids` | UUID[] | Filter by categories | `?category_ids=uuid1&category_ids=uuid2` |
| `topic_ids` | UUID[] | Filter by topics | `?topic_ids=uuid1&topic_ids=uuid2` |
| `status_ids` | UUID[] | Filter by test statuses | `?status_ids=uuid1&status_ids=uuid2` |
| `test_ids` | UUID[] | Filter specific tests | `?test_ids=uuid1&test_ids=uuid2` |
| `test_type_ids` | UUID[] | Filter by test types | `?test_type_ids=uuid1&test_type_ids=uuid2` |

### Test Run Filters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `test_run_id` | UUID | Single test run (legacy) | `?test_run_id=uuid` |
| `test_run_ids` | UUID[] | Multiple test runs | `?test_run_ids=uuid1&test_run_ids=uuid2` |

### User-Related Filters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `user_ids` | UUID[] | Filter by test creators | `?user_ids=uuid1&user_ids=uuid2` |
| `assignee_ids` | UUID[] | Filter by assignees | `?assignee_ids=uuid1&assignee_ids=uuid2` |
| `owner_ids` | UUID[] | Filter by test owners | `?owner_ids=uuid1&owner_ids=uuid2` |

### Other Filters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `prompt_ids` | UUID[] | Filter by prompts | `?prompt_ids=uuid1&prompt_ids=uuid2` |
| `priority_min` | int | Minimum priority (inclusive) | `?priority_min=1` |
| `priority_max` | int | Maximum priority (inclusive) | `?priority_max=5` |
| `tags` | string[] | Filter by tags (AND logic) | `?tags=urgent&tags=regression` |

### Date Range Filters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `start_date` | ISO date | Start date (overrides months) | `?start_date=2024-01-01` |
| `end_date` | ISO date | End date (overrides months) | `?end_date=2024-12-31` |
| `months` | int | Historical months (default: 6) | `?months=12` |

## Multiple Value Support

All list-based filters support multiple values using repeated parameters:

### Multiple Test Runs
```bash
# Multiple test runs
curl 'http://localhost:8080/test_results/stats?test_run_ids=uuid1&test_run_ids=uuid2' -H 'Authorization: Bearer YOUR_TOKEN'

# Backward compatibility (combines both)
curl 'http://localhost:8080/test_results/stats?test_run_id=uuid1&test_run_ids=uuid2' -H 'Authorization: Bearer YOUR_TOKEN'
```

### Multiple Behaviors/Categories/Topics
```bash
# Multiple behaviors
curl 'http://localhost:8080/test_results/stats?behavior_ids=uuid1&behavior_ids=uuid2' -H 'Authorization: Bearer YOUR_TOKEN'

# Multiple categories
curl 'http://localhost:8080/test_results/stats?category_ids=uuid1&category_ids=uuid2' -H 'Authorization: Bearer YOUR_TOKEN'
```

### Multiple Users/Teams
```bash
# Multiple team members
curl 'http://localhost:8080/test_results/stats?user_ids=dev1&user_ids=dev2&assignee_ids=lead1' -H 'Authorization: Bearer YOUR_TOKEN'
```

### Multiple Tags
```bash
# Multiple tags (AND logic - tests must have ALL tags)
curl 'http://localhost:8080/test_results/stats?tags=urgent&tags=healthcare' -H 'Authorization: Bearer YOUR_TOKEN'
```

## Response Structure

### Summary Mode Response
```json
{
  "overall_pass_rates": {
    "total": 150,
    "passed": 75,
    "failed": 75,
    "pass_rate": 50.0
  },
  "metadata": {
    "mode": "summary",
    "total_test_results": 150,
    "total_test_runs": 5,
    "start_date": "2024-06-01T00:00:00",
    "end_date": "2024-12-01T00:00:00",
    "organization_id": "org-uuid",
    "available_metrics": ["Answer Fluency", "Answer Relevancy"],
    "available_behaviors": ["Factual Accuracy", "Reasoning"],
    "available_categories": ["RAG Systems", "Chatbots"],
    "available_topics": ["Healthcare", "Finance"]
  }
}
```

### Metrics Mode Response
```json
{
  "metric_pass_rates": {
    "Answer Fluency": {
      "total": 150,
      "passed": 90,
      "failed": 60,
      "pass_rate": 60.0
    },
    "Answer Relevancy": {
      "total": 150,
      "passed": 135,
      "failed": 15,
      "pass_rate": 90.0
    }
  },
  "metadata": { "mode": "metrics", ... }
}
```

### Complete Mode Sections

| Mode | Response Sections |
|------|------------------|
| `all` | All sections below |
| `summary` | `overall_pass_rates` + `metadata` |
| `metrics` | `metric_pass_rates` + `metadata` |
| `behavior` | `behavior_pass_rates` + `metadata` |
| `category` | `category_pass_rates` + `metadata` |
| `topic` | `topic_pass_rates` + `metadata` |
| `overall` | `overall_pass_rates` + `metadata` |
| `timeline` | `timeline` + `metadata` |
| `test_runs` | `test_run_summary` + `metadata` |

## Performance Optimization

### Choose the Right Mode

**For Dashboard Widgets**
```bash
# Ultra-fast, minimal data
curl 'http://localhost:8080/test_results/stats?mode=summary&months=1' -H 'Authorization: Bearer YOUR_TOKEN'
```

**For Specific Analysis**
```bash
# Only metrics data
curl 'http://localhost:8080/test_results/stats?mode=metrics&test_set_ids=uuid' -H 'Authorization: Bearer YOUR_TOKEN'

# Only behavior trends
curl 'http://localhost:8080/test_results/stats?mode=behavior&months=6' -H 'Authorization: Bearer YOUR_TOKEN'
```

**For Time-based Charts**
```bash
# Timeline data only
curl 'http://localhost:8080/test_results/stats?mode=timeline&start_date=2024-01-01&end_date=2024-06-30' -H 'Authorization: Bearer YOUR_TOKEN'
```

### Use Targeted Filters

**Reduce Dataset Size**
```bash
# Specific test set analysis
curl 'http://localhost:8080/test_results/stats?test_set_ids=uuid&mode=metrics' -H 'Authorization: Bearer YOUR_TOKEN'

# High-priority tests only
curl 'http://localhost:8080/test_results/stats?priority_min=3&mode=summary' -H 'Authorization: Bearer YOUR_TOKEN'

# Recent data only
curl 'http://localhost:8080/test_results/stats?months=1&mode=timeline' -H 'Authorization: Bearer YOUR_TOKEN'
```

## Complete Examples

### Dashboard Implementation

**Executive Dashboard (Ultra-fast)**
```bash
curl 'http://localhost:8080/test_results/stats?mode=summary&months=1' -H 'Authorization: Bearer YOUR_TOKEN'
# Response time: ~50ms, Data size: ~5%
```

**Team Performance Dashboard**
```bash
curl 'http://localhost:8080/test_results/stats?mode=test_runs&assignee_ids=lead1&assignee_ids=lead2&months=3' -H 'Authorization: Bearer YOUR_TOKEN'
# Shows test run performance for specific team leads
```

### Analytics Use Cases

**Metric Performance Analysis**
```bash
curl 'http://localhost:8080/test_results/stats?mode=metrics&test_set_ids=regression_suite&months=12' -H 'Authorization: Bearer YOUR_TOKEN'
# 12-month metric trends for regression test suite
```

**Behavior Comparison**
```bash
curl 'http://localhost:8080/test_results/stats?mode=behavior&behavior_ids=uuid1&behavior_ids=uuid2&start_date=2024-01-01&end_date=2024-06-30' -H 'Authorization: Bearer YOUR_TOKEN'
# Compare specific behaviors over date range
```

**Category Trends**
```bash
curl 'http://localhost:8080/test_results/stats?mode=category&category_ids=chatbot&months=6' -H 'Authorization: Bearer YOUR_TOKEN'
# 6-month category performance trends
```

### Advanced Filtering

**Urgent Healthcare Tests**
```bash
curl 'http://localhost:8080/test_results/stats?behavior_ids=healthcare_uuid&tags=urgent&priority_min=4&mode=summary' -H 'Authorization: Bearer YOUR_TOKEN'
# High-priority urgent healthcare test performance
```

**Team Regression Analysis**
```bash
curl 'http://localhost:8080/test_results/stats?tags=regression&assignee_ids=dev1&assignee_ids=dev2&start_date=2024-01-01&mode=test_runs' -H 'Authorization: Bearer YOUR_TOKEN'
# Regression test performance by team members
```

**Multi-dimensional Analysis**
```bash
curl 'http://localhost:8080/test_results/stats?test_set_ids=suite1&test_set_ids=suite2&behavior_ids=behavior1&category_ids=category1&priority_min=2&mode=all' -H 'Authorization: Bearer YOUR_TOKEN'
# Complete analysis across multiple dimensions
```

## Best Practices

### Performance Best Practices

1. **Use Specific Modes**: Always use the most specific mode for your use case
2. **Apply Filters**: Reduce dataset size with targeted filters
3. **Limit Time Ranges**: Use shorter time periods when possible
4. **Cache Results**: Cache responses for repeated queries

### Query Optimization

**Good Examples:**
```bash
# Lightweight dashboard widget
?mode=summary&months=1

# Focused metric analysis  
?mode=metrics&test_set_ids=uuid&months=3

# Targeted behavior comparison
?mode=behavior&behavior_ids=uuid1&behavior_ids=uuid2&months=6
```

**Avoid These:**
```bash
# Unnecessarily broad queries
?mode=all&months=24

# Unfocused large datasets
?mode=all  # without any filters
```

### Error Handling

The API provides clear validation errors:

```json
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": ["query", "priority_max"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "abc"
    }
  ]
}
```

### Integration Tips

**React/JavaScript Usage:**
```javascript
// Dashboard widget
const summaryData = await fetch('/test_results/stats?mode=summary&months=1');

// Chart data
const metricsData = await fetch('/test_results/stats?mode=metrics&test_set_ids=' + testSetId);

// Timeline chart
const timelineData = await fetch('/test_results/stats?mode=timeline&months=6');
```

**Python Usage:**
```python
import requests

# Dashboard summary
response = requests.get(
    "http://localhost:8080/test_results/stats",
    headers={"Authorization": f"Bearer {token}"},
    params={"mode": "summary", "months": 1}
)

# Multi-filter analysis
response = requests.get(
    "http://localhost:8080/test_results/stats",
    headers={"Authorization": f"Bearer {token}"},
    params={
        "mode": "behavior",
        "behavior_ids": ["uuid1", "uuid2"],
        "priority_min": 3,
        "months": 6
    }
)
```

This endpoint provides enterprise-level analytics capabilities with the flexibility and performance needed for production dashboards and detailed analysis workflows.
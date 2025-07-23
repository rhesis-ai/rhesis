# OData Query Guide

This guide covers how to use OData queries with the Rhesis backend API. All examples in this guide have been tested and verified to work with the current implementation.

## Table of Contents

1. [Basic Concepts](#basic-concepts)
2. [Comparison Operators](#comparison-operators)
3. [String Functions](#string-functions)
4. [Navigation Properties](#navigation-properties)
5. [Logical Operators](#logical-operators)
6. [Advanced Features](#advanced-features)
7. [Complete Examples](#complete-examples)
8. [Best Practices](#best-practices)

## Basic Concepts

OData (Open Data Protocol) is a REST-based protocol for querying and updating data. In Rhesis, you can use OData filters with the `$filter` query parameter.

### URL Format
```
GET /endpoint?$filter=<odata-expression>
```

### Authentication
All requests require a Bearer token:
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" "URL"
```

## Comparison Operators

### Equality Operators

**Equal (`eq`)**
```bash
# Find tests with priority = 1
GET /tests?$filter=priority eq 1

# Find behaviors with specific name
GET /behaviors?$filter=name eq 'Test Behavior'
```

**Not Equal (`ne`)**
```bash
# Find tests where priority is not null
GET /tests?$filter=priority ne null

# Find behaviors not named 'Test'
GET /behaviors?$filter=name ne 'Test'
```

### Comparison Operators

**Greater Than (`gt`)**
```bash
# Find tests with priority > 0
GET /tests?$filter=priority gt 0
```

**Less Than (`lt`)**
```bash
# Find tests with priority < 5
GET /tests?$filter=priority lt 5
```

**Greater Than or Equal (`ge`)**
```bash
# Find tests with priority >= 1
GET /tests?$filter=priority ge 1
```

**Less Than or Equal (`le`)**
```bash
# Find tests with priority <= 5
GET /tests?$filter=priority le 5
```

## String Functions

All string functions use function-style syntax: `function(field, value)`

### Contains
```bash
# Find behaviors containing 'Test' in name
GET /behaviors?$filter=contains(name,'Test')

# Case-insensitive search
GET /behaviors?$filter=contains(tolower(name),'test')
```

### Starts With
```bash
# Find behaviors starting with 'Test'
GET /behaviors?$filter=startswith(name,'Test')
```

### Ends With
```bash
# Find behaviors ending with 'Behavior'
GET /behaviors?$filter=endswith(name,'Behavior')
```

### Case Conversion

**To Lower Case (`tolower`)**
```bash
# Case-insensitive search using tolower
GET /behaviors?$filter=contains(tolower(name),'test')
```

**To Upper Case (`toupper`)**
```bash
# Case-insensitive search using toupper
GET /behaviors?$filter=contains(toupper(name),'TEST')
```

## Navigation Properties

Navigate through relationships using the `/` operator: `relationship/field`

### Behavior Navigation
```bash
# Find tests by behavior name
GET /tests?$filter=behavior/name eq 'Test Behavior'

# Case-insensitive behavior search
GET /tests?$filter=contains(tolower(behavior/name),'rel')
```

### Status Navigation
```bash
# Find tests by status
GET /tests?$filter=status/name eq 'New'

# Find active behaviors
GET /behaviors?$filter=status/name eq 'Active'
```

### Prompt Navigation
```bash
# Find tests by prompt content
GET /tests?$filter=contains(prompt/content,'test')
```

### Topic Navigation
```bash
# Find tests by topic
GET /tests?$filter=topic/name eq 'Security'
```

### Category Navigation
```bash
# Find tests by category
GET /tests?$filter=category/name eq 'Performance'
```

## Logical Operators

### AND Operator
```bash
# Multiple conditions must be true
GET /tests?$filter=status/name eq 'New' and priority ne null
```

### OR Operator
```bash
# Either condition can be true
GET /tests?$filter=priority eq 1 or priority eq 2
```

### NOT Operator
```bash
# Negate a condition (use parentheses)
GET /tests?$filter=not (priority eq 1)
```

### Complex Expressions with Parentheses
```bash
# Group conditions with parentheses
GET /tests?$filter=(status/name eq 'New' and priority ne null) or contains(prompt/content,'test')
```

## Advanced Features

### Sorting
Use `sort_by` and `sort_order` parameters:
```bash
# Sort by creation date, newest first
GET /tests?sort_by=created_at&sort_order=desc

# Sort by priority, lowest first
GET /tests?sort_by=priority&sort_order=asc
```

### Pagination
Use `skip` and `limit` parameters:
```bash
# Get 10 items starting from item 20
GET /tests?skip=20&limit=10

# Combine with filtering
GET /tests?$filter=status/name eq 'New'&skip=0&limit=50
```

### Combining Parameters
```bash
# Filter + Sort + Paginate
GET /tests?$filter=contains(tolower(behavior/name),'rel')&sort_by=created_at&sort_order=desc&skip=0&limit=25
```

## Complete Examples

### Example 1: Case-Insensitive Behavior Search
```bash
# Find all tests where behavior name contains 'rel' (case-insensitive)
GET /tests?$filter=contains(tolower(behavior/name),'rel')
```

### Example 2: Complex Multi-Condition Filter
```bash
# Find tests that are either:
# - New status with non-null priority, OR
# - Have 'test' in prompt content
GET /tests?$filter=(status/name eq 'New' and priority ne null) or contains(prompt/content,'test')
```

### Example 3: Advanced Search with Sorting
```bash
# Find active behaviors, sort by name
GET /behaviors?$filter=status/name eq 'Active'&sort_by=name&sort_order=asc
```

### Example 4: Navigation with String Functions
```bash
# Find tests where behavior description contains 'robust' (case-insensitive)
GET /tests?$filter=contains(tolower(behavior/description),'robust')
```

## Best Practices

### 1. Use Case-Insensitive Searches
For user-friendly searches, always use `tolower()` or `toupper()`:
```bash
# Good: Case-insensitive
GET /behaviors?$filter=contains(tolower(name),'reliability')

# Avoid: Case-sensitive (user must know exact case)
GET /behaviors?$filter=contains(name,'Reliability')
```

### 2. Use Navigation Properties for Related Data
Instead of multiple API calls, use navigation:
```bash
# Good: Single request with navigation
GET /tests?$filter=behavior/name eq 'Reliability'

# Avoid: Multiple requests (less efficient)
# 1. GET /behaviors?$filter=name eq 'Reliability'
# 2. GET /tests?$filter=behavior_id eq 'uuid-from-step-1'
```

### 3. Use Parentheses for Complex Logic
Make complex expressions clear with parentheses:
```bash
# Good: Clear precedence
GET /tests?$filter=(status/name eq 'New' or status/name eq 'Active') and priority gt 0

# Avoid: Ambiguous precedence
GET /tests?$filter=status/name eq 'New' or status/name eq 'Active' and priority gt 0
```

### 4. Combine Filtering with Pagination
Always use pagination for potentially large result sets:
```bash
# Good: Paginated results
GET /tests?$filter=status/name eq 'New'&limit=50

# Avoid: Potentially huge response
GET /tests?$filter=status/name eq 'New'
```

### 5. URL Encoding
Remember to URL-encode your queries:
```bash
# Space becomes %20, / becomes %2F, ' becomes %27
GET /tests?%24filter=contains(behavior%2Fname,%27Test%27)
```

## Error Handling

### Common Errors

**Invalid Field Names**
```json
{
  "detail": "Invalid filter. Must use valid fields: field1, field2, ..."
}
```

**Parse Errors**
```json
{
  "detail": "Error processing filter: Failed to parse at: Token(...)"
}
```

**Invalid Syntax**
Use function-style syntax for string operations:
```bash
# Correct
GET /tests?$filter=contains(behavior/name,'test')

# Incorrect (will cause parse error)
GET /tests?$filter=behavior/name contains 'test'
```

## Available Endpoints

The following endpoints support OData filtering:

- `/tests` - Test entities
- `/behaviors` - Behavior entities  
- `/topics` - Topic entities
- `/categories` - Category entities
- `/test-sets` - Test set entities
- `/test-runs` - Test run entities
- `/test-results` - Test result entities
- `/prompts` - Prompt entities
- `/metrics` - Metric entities
- `/projects` - Project entities

Each endpoint supports the navigation properties defined in its model relationships.

---

*This documentation was generated and tested on the current Rhesis backend implementation. All examples have been verified to work correctly.* 
"""Seed analysis queries

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-01-15

Seeds the analysis_queries table with comprehensive analysis prompts.
"""
from alembic import op
from src.utils.settings import settings

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


SECURITY_QUERY = '''You are an expert security auditor performing a comprehensive security analysis of this codebase.

## Analysis Scope

### OWASP Top 10 Vulnerabilities
- Broken Access Control, Cryptographic Failures, Injection
- Insecure Design, Security Misconfiguration, Vulnerable Components
- Authentication Failures, Data Integrity Failures, Logging Failures, SSRF

### Secrets and Credentials
- Hardcoded API keys, tokens, passwords
- Exposed credentials in configuration files

### Input Validation
- Missing input sanitization, Path traversal, XXE, SSTI

### Authentication & Session Management
- Insecure session handling, Missing CSRF protection, JWT vulnerabilities

## Output Format
Return a JSON array of findings:
```json
{
  "severity": "critical|high|medium|low|info",
  "title": "Brief vulnerability title",
  "description": "Detailed explanation",
  "file_path": "path/to/file.py",
  "line_start": 42,
  "line_end": 45,
  "recommended_action": "Steps to remediate",
  "code_suggestion": "Secure code example",
  "confidence_score": 0.95
}
```
Output ONLY a valid JSON array.'''


DATABASE_QUERY = '''You are a database performance expert analyzing this codebase for database-related issues.

## Analysis Scope

### Query Performance
- N+1 Query Problems, Missing Indexes, Full Table Scans, Inefficient Joins

### ORM Anti-Patterns
- Lazy Loading Traps, Missing Relationships, Raw SQL bypassing ORM

### Connection Management
- Connection Leaks, Missing Pooling, Pool Exhaustion

### Transaction Management
- Missing Transactions, Deadlock Risks, Isolation Issues

### SQL Injection Risks
- String Concatenation in Queries, Missing Parameterization

## Output Format
Return a JSON array:
```json
{
  "severity": "critical|high|medium|low|info",
  "title": "Issue title",
  "description": "Detailed explanation",
  "file_path": "path/to/file.py",
  "line_start": 100,
  "line_end": 115,
  "recommended_action": "Optimization steps",
  "code_suggestion": "Optimized code",
  "confidence_score": 0.85
}
```
Output ONLY a valid JSON array.'''


API_QUERY = '''You are an API design expert analyzing this codebase for REST API issues.

## Analysis Scope

### RESTful Design
- HTTP Method Misuse, URL Structure, Idempotency

### Input Validation
- Missing Validation, Schema Validation, Size Limits

### Error Handling
- Inconsistent Errors, Information Disclosure, Status Misuse

### Authentication & Authorization
- Unprotected Endpoints, Authorization Gaps, Rate Limiting

### Pagination & Documentation
- Missing Pagination, Incomplete Schemas

## Output Format
Return a JSON array:
```json
{
  "severity": "critical|high|medium|low|info",
  "title": "Issue title",
  "description": "Detailed explanation",
  "file_path": "path/to/routes.py",
  "line_start": 50,
  "line_end": 75,
  "recommended_action": "How to fix",
  "code_suggestion": "Proper implementation",
  "confidence_score": 0.9
}
```
Output ONLY a valid JSON array.'''


PERFORMANCE_QUERY = '''You are a performance optimization expert analyzing this codebase.

## Analysis Scope

### Algorithm Complexity
- O(n²) or Worse, Inefficient Data Structures, Repeated Computations

### Memory Management
- Memory Leaks, Large Object Allocation, Unbounded Caches

### Async/Concurrency
- Blocking in Async Code, Missing Await, Race Conditions

### I/O Optimization
- Synchronous I/O, Missing Batch Operations

### Resource Management
- Unclosed Resources, Missing Timeouts

## Output Format
Return a JSON array:
```json
{
  "severity": "critical|high|medium|low|info",
  "title": "Performance issue",
  "description": "Analysis with impact",
  "file_path": "path/to/file.py",
  "line_start": 200,
  "line_end": 250,
  "recommended_action": "Optimization steps",
  "code_suggestion": "Optimized code",
  "confidence_score": 0.88
}
```
Output ONLY a valid JSON array.'''


ARCHITECTURE_QUERY = '''You are a software architect analyzing this codebase for architectural issues.

## Analysis Scope

### Dependency Management
- Circular Dependencies, Dependency Inversion Violations, Coupling Issues

### SOLID Principles
- Single Responsibility, Open/Closed, Liskov, Interface Segregation, DI

### Layer Violations
- Bypassing Layers, Mixed Concerns

### Code Organization
- God Classes (>500 lines), God Functions (>50 lines)

### Design Patterns
- Missing Patterns, Anti-Patterns, Over-Engineering

## Output Format
Return a JSON array:
```json
{
  "severity": "critical|high|medium|low|info",
  "title": "Architectural issue",
  "description": "Problem and implications",
  "file_path": "path/to/module.py",
  "line_start": 1,
  "line_end": 100,
  "recommended_action": "Refactoring strategy",
  "code_suggestion": "Improved structure",
  "confidence_score": 0.82
}
```
Output ONLY a valid JSON array.'''


TESTING_QUERY = '''You are a testing expert analyzing this codebase for test coverage gaps.

## Analysis Scope

### Coverage Gaps
- Untested Public APIs, Untested Business Logic, Missing Edge Cases

### Test Quality
- Tests Without Assertions, Weak Assertions, Implementation-Coupled Tests

### Flaky Patterns
- Time-Dependent Tests, Order-Dependent Tests, External Dependencies

### Mock Issues
- Missing Mocks, Over-Mocking, Stale Mocks

## Output Format
Return a JSON array:
```json
{
  "severity": "critical|high|medium|low|info",
  "title": "Testing issue",
  "description": "Gap or quality issue",
  "file_path": "path/to/file.py",
  "line_start": 30,
  "line_end": 50,
  "recommended_action": "Tests to add",
  "code_suggestion": "Example test",
  "confidence_score": 0.9
}
```
Output ONLY a valid JSON array.'''


CODE_QUALITY_QUERY = '''You are a code quality expert analyzing this codebase.

## Analysis Scope

### Code Smells
- Long Methods (>30 lines), Large Classes (>300 lines), Long Parameter Lists

### Naming & Complexity
- Unclear Names, High Cyclomatic Complexity (>10), Deep Nesting (>3)

### Documentation
- Missing Docstrings, Outdated Comments, Missing Type Hints

### Dead Code
- Unused Functions, Unused Variables, Unreachable Code

### Error Handling
- Bare Except, Swallowed Exceptions

## Output Format
Return a JSON array:
```json
{
  "severity": "critical|high|medium|low|info",
  "title": "Code quality issue",
  "description": "Issue and why it matters",
  "file_path": "path/to/file.py",
  "line_start": 45,
  "line_end": 120,
  "recommended_action": "How to refactor",
  "code_suggestion": "Cleaner code",
  "confidence_score": 0.87
}
```
Output ONLY a valid JSON array.'''


GENERAL_QUERY = '''You are a senior software engineer performing a comprehensive code review.

## Analysis Dimensions

### Security (Critical)
- Injection, Auth issues, Hardcoded secrets

### Performance
- Algorithm complexity, Memory leaks, Blocking operations

### Architecture
- SOLID violations, Circular dependencies, Layer violations

### Testing
- Untested critical paths, Test quality

### Code Quality
- Code smells, Documentation gaps, Dead code

## Output Format
Return a JSON array:
```json
{
  "severity": "critical|high|medium|low|info",
  "title": "Issue title",
  "description": "Detailed explanation",
  "file_path": "path/to/file.py",
  "line_start": 10,
  "line_end": 25,
  "recommended_action": "How to fix",
  "code_suggestion": "Example fix",
  "confidence_score": 0.85
}
```
Output ONLY a valid JSON array.'''


def upgrade():
    schema = settings.database_schema
    op.execute(f"""
        INSERT INTO {schema}.analysis_queries
        (category, name, description, query_text, is_default, priority, expected_output_format)
        VALUES
        ('security', 'comprehensive_security_scan',
         'Security analysis covering OWASP Top 10, secrets, authentication',
         $q${SECURITY_QUERY}$q$, true, 100, 'json'),

        ('database', 'database_patterns_scan',
         'Database performance analysis including N+1, indexing, transactions',
         $q${DATABASE_QUERY}$q$, true, 100, 'json'),

        ('api', 'api_design_scan',
         'REST API design review covering validation, errors, auth',
         $q${API_QUERY}$q$, true, 100, 'json'),

        ('performance', 'performance_bottlenecks_scan',
         'Performance analysis covering algorithms, memory, async, I/O',
         $q${PERFORMANCE_QUERY}$q$, true, 100, 'json'),

        ('architecture', 'architecture_patterns_scan',
         'Architecture review covering SOLID, dependencies, design patterns',
         $q${ARCHITECTURE_QUERY}$q$, true, 100, 'json'),

        ('testing', 'test_coverage_scan',
         'Testing analysis covering coverage gaps, quality, flakiness',
         $q${TESTING_QUERY}$q$, true, 100, 'json'),

        ('code_quality', 'code_quality_scan',
         'Code quality analysis covering smells, complexity, documentation',
         $q${CODE_QUALITY_QUERY}$q$, true, 100, 'json'),

        ('general', 'general_code_review',
         'Comprehensive review covering security, performance, architecture',
         $q${GENERAL_QUERY}$q$, true, 100, 'json');
    """)


def downgrade():
    schema = settings.database_schema
    op.execute(f"""
        DELETE FROM {schema}.analysis_queries
        WHERE name IN (
            'comprehensive_security_scan',
            'database_patterns_scan',
            'api_design_scan',
            'performance_bottlenecks_scan',
            'architecture_patterns_scan',
            'test_coverage_scan',
            'code_quality_scan',
            'general_code_review'
        );
    """)

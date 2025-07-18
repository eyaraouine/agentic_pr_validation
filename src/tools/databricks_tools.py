# Azure Databricks Validation Tools

from crewai_tools import tool
from typing import Dict, Any, List, Optional
import re
import ast

from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("tools.databricks_tools")


@tool("check_databricks_naming")
def check_databricks_naming_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check Databricks notebook naming conventions

    Args:
        files: List of Databricks files to validate

    Returns:
        Validation results with violations and suggestions
    """
    logger.info(f"Checking naming conventions for {len(files)} Databricks files")

    violations = []
    suggestions = []

    # Naming pattern for notebooks
    naming_pattern = r"^[a-z][a-z0-9_]*$"

    for file in files:
        file_path = file.get("path", "")
        file_name = file_path.split("/")[-1].split(".")[0]  # Get filename without extension

        if not re.match(naming_pattern, file_name):
            violations.append(
                f"{file_path}: Notebook name '{file_name}' does not follow naming convention"
            )
            suggestions.append(
                f"{file_path}: Rename to lowercase with underscores (e.g., 'data_processing_notebook')"
            )

        # Check for meaningful names
        if len(file_name) < 3:
            violations.append(f"{file_path}: Notebook name too short")
            suggestions.append(f"{file_path}: Use descriptive names for notebooks")

    return {
        "checkpoint": "Naming Conventions",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "HIGH"
    }


@tool("check_databricks_security")
def check_databricks_security_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check Databricks security best practices
    """
    logger.info("Checking Databricks security practices")

    violations = []
    suggestions = []

    # Security patterns to detect
    security_risks = [
        (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password detected"),
        (r'token\s*=\s*["\'][^"\']+["\']', "Hardcoded token detected"),
        (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key detected"),
        (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret detected"),
        (r'access_key\s*=\s*["\'][^"\']+["\']', "Hardcoded access key detected")
    ]

    for file in files:
        content = file.get("content", "")

        # Check for hardcoded credentials
        for pattern, risk_message in security_risks:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"{file['path']}: {risk_message}")
                suggestions.append(
                    f"{file['path']}: Use Databricks Secret Scope or Azure Key Vault for sensitive data"
                )

        # Check for proper secret usage
        if "dbutils.secrets.get" in content:
            # Check if secrets are being printed or logged
            if re.search(r'print\s*\(\s*dbutils\.secrets\.get', content):
                violations.append(f"{file['path']}: Printing secrets detected")
                suggestions.append(f"{file['path']}: Never print or log secret values")

            if re.search(r'display\s*\(\s*dbutils\.secrets\.get', content):
                violations.append(f"{file['path']}: Displaying secrets detected")
                suggestions.append(f"{file['path']}: Never display secret values")

        # Check for unsecured data access
        if "spark.read" in content and "option(" in content:
            if re.search(r'\.option\s*\(\s*["\']password["\']', content):
                violations.append(f"{file['path']}: Password passed as option in spark.read")
                suggestions.append(
                    f"{file['path']}: Use secret scope for database passwords in spark connections"
                )

    return {
        "checkpoint": "Security Best Practices",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "CRITICAL"
    }


@tool("check_databricks_performance")
def check_databricks_performance_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check Databricks performance optimization
    """
    logger.info("Checking Databricks performance optimizations")

    violations = []
    suggestions = []

    for file in files:
        content = file.get("content", "")

        # Check for performance anti-patterns

        # 1. Check for collect() on large datasets
        if re.search(r'\.collect\(\)', content):
            if not re.search(r'\.limit\s*\([^)]+\)\.collect\(\)', content):
                violations.append(f"{file['path']}: Using collect() without limit")
                suggestions.append(
                    f"{file['path']}: Use .limit(n).collect() or avoid collect() for large datasets"
                )

        # 2. Check for proper partitioning
        if "spark.read" in content and ".parquet" in content:
            if not re.search(r'\.repartition\s*\(|partitionBy\s*\(', content):
                violations.append(f"{file['path']}: Reading parquet without considering partitioning")
                suggestions.append(
                    f"{file['path']}: Consider using repartition() or partitionBy() for better performance"
                )

        # 3. Check for broadcast joins
        if re.search(r'\.join\s*\(', content):
            if not re.search(r'broadcast\s*\(|\.hint\s*\(\s*["\']broadcast["\']', content):
                violations.append(f"{file['path']}: Join operations without broadcast hint")
                suggestions.append(
                    f"{file['path']}: Use broadcast() for small DataFrames in joins to avoid shuffling"
                )

        # 4. Check for cache usage
        if re.search(r'\.filter\s*\(.*\).*\.filter\s*\(', content) or \
                re.search(r'\.groupBy\s*\(.*\).*\.groupBy\s*\(', content):
            if not re.search(r'\.cache\s*\(\)|\.persist\s*\(', content):
                violations.append(f"{file['path']}: Multiple operations without caching")
                suggestions.append(
                    f"{file['path']}: Use .cache() or .persist() for DataFrames used multiple times"
                )

        # 5. Check for coalesce vs repartition
        if re.search(r'\.repartition\s*\(\s*1\s*\)', content):
            violations.append(f"{file['path']}: Using repartition(1) instead of coalesce(1)")
            suggestions.append(
                f"{file['path']}: Use coalesce(1) instead of repartition(1) to avoid full shuffle"
            )

        # 6. Check cluster configuration comments
        if "spark.conf.set" not in content and len(content) > 500:
            violations.append(f"{file['path']}: No Spark configuration found")
            suggestions.append(
                f"{file['path']}: Add Spark configurations for optimization (e.g., spark.sql.adaptive.enabled)"
            )

    return {
        "checkpoint": "Code Performance",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "HIGH"
    }


@tool("check_databricks_git_integration")
def check_databricks_git_integration_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check Databricks Git integration and practices
    """
    logger.info("Checking Databricks Git integration")

    violations = []
    suggestions = []

    for file in files:
        content = file.get("content", "")
        file_path = file.get("path", "")

        # Check for debugging/test code that shouldn't be in PR
        debug_patterns = [
            (r'#\s*TODO(?!\s*\()', "TODO comment without assignee"),
            (r'#\s*FIXME', "FIXME comment found"),
            (r'#\s*HACK', "HACK comment found"),
            (r'print\s*\(\s*["\']debug', "Debug print statements"),
            (r'#\s*test\s+code', "Test code comments")
        ]

        for pattern, message in debug_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"{file_path}: {message}")
                suggestions.append(f"{file_path}: Remove or address {message.lower()} before merging")

        # Check for proper code organization
        if len(content.split('\n')) > 500:
            # Check if notebook has sections/cells properly defined
            if "# COMMAND ----------" not in content and "# MAGIC" not in content:
                violations.append(f"{file_path}: Large notebook without proper cell separation")
                suggestions.append(
                    f"{file_path}: Use '# COMMAND ----------' to separate logical sections"
                )

        # Check for version/change documentation
        if not re.search(r'#\s*(Author|Created|Modified|Version):', content, re.IGNORECASE):
            violations.append(f"{file_path}: Missing metadata comments")
            suggestions.append(
                f"{file_path}: Add header comments with Author, Created date, and Version"
            )

    return {
        "checkpoint": "Git Integration & Documentation",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "MEDIUM"
    }


@tool("check_databricks_testing")
def check_databricks_testing_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check Databricks testing coverage
    """
    logger.info("Checking Databricks testing practices")

    violations = []
    suggestions = []

    for file in files:
        content = file.get("content", "")
        file_path = file.get("path", "")

        # Check for test functions/cells
        has_tests = any([
            re.search(r'def\s+test_', content),
            re.search(r'#\s*TEST', content, re.IGNORECASE),
            re.search(r'assert\s+', content),
            "unittest" in content,
            "pytest" in content
        ])

        # Check for data validation
        has_data_validation = any([
            re.search(r'\.count\s*\(\)\s*>\s*0', content),
            re.search(r'\.schema', content),
            re.search(r'\.dtypes', content),
            re.search(r'\.describe\s*\(\)', content)
        ])

        # If notebook has business logic but no tests
        if len(content) > 200 and not has_tests:
            violations.append(f"{file_path}: No test functions or assertions found")
            suggestions.append(
                f"{file_path}: Add unit tests or test cells to validate functionality"
            )

        # If notebook processes data but no validation
        if "spark.read" in content and not has_data_validation:
            violations.append(f"{file_path}: No data validation found")
            suggestions.append(
                f"{file_path}: Add data quality checks (row count, schema validation, etc.)"
            )

        # Check for error handling
        if "spark.read" in content or "spark.sql" in content:
            if "try:" not in content and "except" not in content:
                violations.append(f"{file_path}: No error handling for Spark operations")
                suggestions.append(
                    f"{file_path}: Add try-except blocks for data operations"
                )

    return {
        "checkpoint": "Testing Coverage",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "HIGH"
    }


@tool("check_databricks_documentation")
def check_databricks_documentation_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check Databricks code documentation
    """
    logger.info("Checking Databricks documentation")

    violations = []
    suggestions = []

    for file in files:
        content = file.get("content", "")
        file_path = file.get("path", "")

        # Count functions and check for docstrings
        functions = re.findall(r'def\s+(\w+)\s*\([^)]*\):', content)

        for func_name in functions:
            # Check if function has docstring
            func_pattern = rf'def\s+{func_name}\s*\([^)]*\):\s*\n\s*"""'
            if not re.search(func_pattern, content):
                violations.append(f"{file_path}: Function '{func_name}' missing docstring")
                suggestions.append(
                    f"{file_path}: Add docstring to function '{func_name}' explaining purpose and parameters"
                )

        # Check for notebook-level documentation
        lines = content.split('\n')
        if len(lines) > 10:
            # Check first 10 lines for documentation
            header_content = '\n'.join(lines[:10])
            if not re.search(r'#\s*(Purpose|Description|Overview):', header_content, re.IGNORECASE):
                violations.append(f"{file_path}: Missing notebook header documentation")
                suggestions.append(
                    f"{file_path}: Add header comment explaining notebook purpose and usage"
                )

        # Check for inline comments in complex logic
        complex_patterns = [
            r'\.join\s*\(',
            r'\.groupBy\s*\(',
            r'\.agg\s*\(',
            r'\.window\s*\('
        ]

        for pattern in complex_patterns:
            if re.search(pattern, content):
                # Check if there are comments near these operations
                pattern_line = None
                for i, line in enumerate(lines):
                    if re.search(pattern, line):
                        pattern_line = i
                        break

                if pattern_line is not None:
                    # Check 2 lines before and after for comments
                    start = max(0, pattern_line - 2)
                    end = min(len(lines), pattern_line + 3)
                    nearby_lines = lines[start:end]

                    has_comment = any('#' in line for line in nearby_lines)
                    if not has_comment:
                        violations.append(
                            f"{file_path}: Complex operation without explanation near line {pattern_line + 1}"
                        )
                        suggestions.append(
                            f"{file_path}: Add comment explaining the complex operation"
                        )
                        break  # Only report once per file

    return {
        "checkpoint": "Code Documentation",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "MEDIUM"
    }
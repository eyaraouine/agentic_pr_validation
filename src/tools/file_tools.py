# File Analysis Tools for CrewAI

from crewai_tools import tool
from typing import List, Dict, Any, Optional
import json
import re
from pathlib import Path

from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("tools.file_tools")


@tool("analyze_pr_files")
def analyze_pr_files_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze PR files to extract metadata and prepare for validation

    Args:
        files: List of file dictionaries with path, type, change_type, content

    Returns:
        Dictionary with file analysis results including statistics and categorization
    """
    logger.info(f"Analyzing {len(files)} files in PR")

    # Initialize counters
    stats = {
        "total_files": len(files),
        "files_by_type": {},
        "files_by_change_type": {},
        "files_by_technology": {},
        "large_files": [],
        "potential_issues": []
    }

    # Categorize files
    categorized_files = {
        "adf": [],
        "databricks": [],
        "sql": [],
        "config": [],
        "other": []
    }

    for file in files:
        file_path = file.get("path", "")
        file_type = file.get("type", "unknown")
        change_type = file.get("change_type", "unknown")
        content = file.get("content", "")

        # Update statistics
        stats["files_by_type"][file_type] = stats["files_by_type"].get(file_type, 0) + 1
        stats["files_by_change_type"][change_type] = stats["files_by_change_type"].get(change_type, 0) + 1

        # Detect technology
        technology = _detect_technology_from_path(file_path)
        stats["files_by_technology"][technology] = stats["files_by_technology"].get(technology, 0) + 1

        # Check file size
        if content and len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            stats["large_files"].append(file_path)
            stats["potential_issues"].append(f"Large file detected: {file_path}")

        # Categorize file
        if technology == "Azure Data Factory":
            categorized_files["adf"].append(file)
        elif technology == "Azure Databricks":
            categorized_files["databricks"].append(file)
        elif technology == "Azure SQL":
            categorized_files["sql"].append(file)
        elif file_path.endswith(('.yaml', '.yml', '.json', '.xml')):
            categorized_files["config"].append(file)
        else:
            categorized_files["other"].append(file)

        # Quick security scan
        if content:
            security_issues = _quick_security_scan(content, file_path)
            if security_issues:
                stats["potential_issues"].extend(security_issues)

    result = {
        "statistics": stats,
        "categorized_files": categorized_files,
        "technologies_present": list(stats["files_by_technology"].keys()),
        "validation_required": len(categorized_files["adf"]) > 0 or
                               len(categorized_files["databricks"]) > 0 or
                               len(categorized_files["sql"]) > 0
    }

    logger.info(f"File analysis complete. Technologies detected: {result['technologies_present']}")

    return result


@tool("detect_technologies")
def detect_technologies_tool(file_analysis: Dict[str, Any]) -> List[str]:
    """
    Detect technologies used based on file analysis results

    Args:
        file_analysis: Results from analyze_pr_files_tool

    Returns:
        List of detected technologies requiring validation
    """
    technologies = []
    categorized_files = file_analysis.get("categorized_files", {})

    # Check each technology category
    if categorized_files.get("adf"):
        technologies.append("Azure Data Factory")
        logger.info(f"Detected Azure Data Factory - {len(categorized_files['adf'])} files")

    if categorized_files.get("databricks"):
        technologies.append("Azure Databricks")
        logger.info(f"Detected Azure Databricks - {len(categorized_files['databricks'])} files")

    if categorized_files.get("sql"):
        technologies.append("Azure SQL")
        logger.info(f"Detected Azure SQL - {len(categorized_files['sql'])} files")

    # Additional detection based on file content patterns
    for category, files in categorized_files.items():
        if category in ["adf", "databricks", "sql"]:
            continue

        for file in files:
            content = file.get("content", "")
            if content:
                # Check for technology-specific patterns in config files
                if _contains_adf_patterns(content) and "Azure Data Factory" not in technologies:
                    technologies.append("Azure Data Factory")
                elif _contains_databricks_patterns(content) and "Azure Databricks" not in technologies:
                    technologies.append("Azure Databricks")
                elif _contains_sql_patterns(content) and "Azure SQL" not in technologies:
                    technologies.append("Azure SQL")

    logger.info(f"Final technology detection: {technologies}")
    return technologies


def _detect_technology_from_path(file_path: str) -> str:
    """
    Detect technology based on file path patterns
    """
    path_lower = file_path.lower()

    # Azure Data Factory patterns
    adf_patterns = [
        r"datafactory/",
        r"adf/",
        r"pipeline.*\.json$",
        r"dataset.*\.json$",
        r"linkedservice.*\.json$",
        r"dataflow.*\.json$",
        r"trigger.*\.json$"
    ]

    for pattern in adf_patterns:
        if re.search(pattern, path_lower):
            return "Azure Data Factory"

    # Azure Databricks patterns
    databricks_patterns = [
        r"databricks/",
        r"notebooks?/",
        r".*notebook.*\.py$",
        r".*notebook.*\.scala$",
        r".*notebook.*\.sql$",
        r".*notebook.*\.r$"
    ]

    for pattern in databricks_patterns:
        if re.search(pattern, path_lower):
            return "Azure Databricks"

    # Azure SQL patterns
    sql_patterns = [
        r"\.sql$",
        r"sql/",
        r"stored_procedures?/",
        r"tables?/",
        r"views?/",
        r"functions?/",
        r"triggers?/"
    ]

    for pattern in sql_patterns:
        if re.search(pattern, path_lower):
            return "Azure SQL"

    return "Other"


def _quick_security_scan(content: str, file_path: str) -> List[str]:
    """
    Perform quick security scan on file content
    """
    issues = []

    # Common security patterns to check
    security_patterns = [
        (r"password\s*=\s*[\"'][^\"']+[\"']", "Potential hardcoded password"),
        (r"api[_-]?key\s*=\s*[\"'][^\"']+[\"']", "Potential hardcoded API key"),
        (r"secret\s*=\s*[\"'][^\"']+[\"']", "Potential hardcoded secret"),
        (r"accountkey\s*=\s*[\"'][^\"']+[\"']", "Potential hardcoded account key"),
        (r"connectionstring\s*=\s*[\"'][^\"']+[\"']", "Potential hardcoded connection string"),
        (r"bearer\s+[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+", "Potential hardcoded JWT token")
    ]

    content_lower = content.lower()

    for pattern, message in security_patterns:
        if re.search(pattern, content_lower, re.IGNORECASE):
            issues.append(f"{message} detected in {file_path}")

    return issues


def _contains_adf_patterns(content: str) -> bool:
    """
    Check if content contains ADF-specific patterns
    """
    adf_keywords = [
        '"type": "Pipeline"',
        '"type": "Dataset"',
        '"type": "LinkedService"',
        '"type": "DataFlow"',
        '"type": "Trigger"',
        'Microsoft.DataFactory',
        'datafactory'
    ]

    content_lower = content.lower()
    return any(keyword.lower() in content_lower for keyword in adf_keywords)


def _contains_databricks_patterns(content: str) -> bool:
    """
    Check if content contains Databricks-specific patterns
    """
    databricks_keywords = [
        'dbutils',
        'spark.sql',
        'spark.read',
        'spark.write',
        'databricks',
        'pyspark',
        'spark.conf',
        'sc.parallelize'
    ]

    content_lower = content.lower()
    return any(keyword.lower() in content_lower for keyword in databricks_keywords)


def _contains_sql_patterns(content: str) -> bool:
    """
    Check if content contains SQL-specific patterns
    """
    sql_keywords = [
        'CREATE TABLE',
        'CREATE PROCEDURE',
        'CREATE VIEW',
        'CREATE FUNCTION',
        'CREATE TRIGGER',
        'ALTER TABLE',
        'DROP TABLE',
        'INSERT INTO',
        'UPDATE SET',
        'DELETE FROM'
    ]

    content_upper = content.upper()
    return any(keyword in content_upper for keyword in sql_keywords)
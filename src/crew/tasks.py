# src/crew/tasks.py - Updated version

from crewai import Task
from typing import List, Dict, Any
import json

from src.utils.logger import setup_logger

logger = setup_logger("crew.tasks")


def create_validation_tasks(
        pr_id: str,
        files: List[Dict[str, Any]],
        agents: Dict[str, Any]
) -> List[Task]:
    """
    Create validation tasks based on PR content
    """
    tasks = []

    # Ensure files have proper structure with content
    files_with_content = []
    for file in files:
        file_data = {
            "path": file.get("path", ""),
            "type": file.get("type", "unknown"),
            "change_type": file.get("change_type", "add"),
            "content": file.get("content", "")
        }
        files_with_content.append(file_data)

    # Convert files to JSON string for agent consumption - escape braces for format()
    files_json = json.dumps(files_with_content, indent=2).replace('{', '{{').replace('}', '}}')

    # Task 1: Initial PR Analysis
    task_analyze_pr = Task(
        description=f"""
        Analyze pull request {pr_id} to understand the scope of changes.

        Files data:
        {files_json}

        Tasks:
        1. Review all {len(files)} modified files
        2. Identify the technologies used (Azure Data Factory, Databricks, SQL)
        3. Categorize files by technology and change type
        4. Identify any potential security risks
        5. Prepare a comprehensive file analysis report

        Expected output: A detailed analysis report containing:
        - Technologies detected
        - File statistics by type and technology
        - List of files requiring validation per technology
        - Any immediate concerns or risks identified
        """,
        expected_output="Comprehensive file analysis report with technology detection",
        agent=agents["file_analyst"]
    )
    tasks.append(task_analyze_pr)

    # Separate files by technology for validation tasks
    adf_files = [f for f in files_with_content if f.get("type") == "adf"]
    databricks_files = [f for f in files_with_content if f.get("type") == "databricks"]
    sql_files = [f for f in files_with_content if f.get("type") == "sql"]

    # Task 2: ADF Validation
    if adf_files:
        adf_files_json = json.dumps(adf_files, indent=2).replace('{', '{{').replace('}', '}}')
        task_validate_adf = Task(
            description=f"""
            Validate {len(adf_files)} Azure Data Factory files.

            Files to validate:
            {adf_files_json}

            Use the check_adf_* tools with this exact format for the files parameter.

            Validate against all checkpoints:
            - CRITICAL: Security, ADF Validation, Production Readiness, Error Handling
            - HIGH: Naming Convention, No Impact, Parameterization, Performance, Testing
            - MEDIUM/LOW: Pipeline Pattern, Reusability, Folder Organization, Logging

            For each checkpoint, document violations and provide remediation suggestions.
            """,
            expected_output="List of checkpoint results for ADF with pass/fail status and detailed suggestions",
            agent=agents["adf_specialist"]
        )
        tasks.append(task_validate_adf)

    # Task 3: Databricks Validation
    if databricks_files:
        databricks_files_json = json.dumps(databricks_files, indent=2).replace('{', '{{').replace('}', '}}')
        task_validate_databricks = Task(
            description=f"""
            Validate {len(databricks_files)} Azure Databricks files.

            Files to validate:
            {databricks_files_json}

            Use the check_databricks_* tools with this exact format for the files parameter.

            Validate against all checkpoints:
            - CRITICAL: Security Best Practices
            - HIGH: Naming, Performance, Git Integration, Testing, Validation
            - MEDIUM/LOW: Pattern, Reusability, Logging, Documentation

            Check for performance optimizations, security issues, and best practices.
            """,
            expected_output="List of checkpoint results for Databricks with detailed performance suggestions",
            agent=agents["databricks_specialist"]
        )
        tasks.append(task_validate_databricks)

    # Task 4: SQL Validation
    if sql_files:
        sql_files_json = json.dumps(sql_files, indent=2).replace('{', '{{').replace('}', '}}')
        task_validate_sql = Task(
            description=f"""
            Validate {len(sql_files)} Azure SQL files.

            Files to validate:
            {sql_files_json}

            Use the check_sql_* tools with this exact format for the files parameter.

            Validate against all checkpoints:
            - CRITICAL: Access Control
            - HIGH: Constraints, Version Control
            - MEDIUM: Stored Procedures, Schemas, Naming, Data Types, Logging
            - LOW: Code Formatting

            Check for security vulnerabilities and best practices.
            """,
            expected_output="List of checkpoint results for SQL with security and performance recommendations",
            agent=agents["sql_specialist"]
        )
        tasks.append(task_validate_sql)

    # Task 5: Generate Report
    task_generate_report = Task(
        description=f"""
        Generate a comprehensive validation report for PR {pr_id}.

        Compile all validation results and:
        1. Determine overall production readiness (READY if no CRITICAL violations)
        2. Create executive summary with key metrics
        3. Generate prioritized remediation plan with effort estimation
        4. Format report for clarity and actionability

        Include:
        - Overall status
        - Issues by severity
        - Technologies validated
        - Remediation steps
        - Effort estimation
        """,
        expected_output="Complete PRValidationReport with status, violations, suggestions, and remediation plan",
        agent=agents["report_generator"],
        context=tasks[1:] if len(tasks) > 1 else []
    )
    tasks.append(task_generate_report)

    logger.info(f"Created {len(tasks)} validation tasks for PR {pr_id}")
    return tasks


def create_remediation_task(
        pr_id: str,
        validation_report: Dict[str, Any],
        agents: Dict[str, Any]
) -> Task:
    """
    Create a task for generating detailed remediation steps

    Args:
        pr_id: Pull request identifier
        validation_report: Previous validation results
        agents: Dictionary of available agents

    Returns:
        CrewAI task for remediation planning
    """
    critical_issues = [
        issue for issue in validation_report.get("checkpoint_results", [])
        if issue["status"] == "FAIL" and issue["severity"] == "CRITICAL"
    ]

    task_remediation = Task(
        description=f"""
        Create a detailed remediation plan for PR {pr_id} with {len(critical_issues)} critical issues:

        For each critical issue:
        1. Analyze the root cause
        2. Provide step-by-step fix instructions
        3. Include code examples where applicable
        4. Suggest preventive measures for future
        5. Estimate time to fix

        Critical issues to address:
        {json.dumps(critical_issues, indent=2).replace('{', '{{').replace('}', '}}')}

        The plan should be immediately actionable by developers.
        """,
        expected_output="Detailed remediation plan with code examples and time estimates",
        agent=agents["report_generator"]
    )

    return task_remediation
# Task definitions for PR Validation Crew

from crewai import Task
from typing import List, Dict, Any

from src.utils.logger import setup_logger

logger = setup_logger("crew.tasks")


def create_validation_tasks(
        pr_id: str,
        files: List[Dict[str, Any]],
        agents: Dict[str, Any]
) -> List[Task]:
    """
    Create validation tasks based on PR content

    Args:
        pr_id: Pull request identifier
        files: List of modified files
        agents: Dictionary of available agents

    Returns:
        List of CrewAI tasks for validation
    """
    tasks = []

    # Task 1: Initial PR Analysis
    task_analyze_pr = Task(
        description=f"""
        Analyze pull request {pr_id} to understand the scope of changes:

        1. Review all {len(files)} modified files
        2. Identify the technologies used (Azure Data Factory, Databricks, SQL)
        3. Categorize files by technology and change type
        4. Identify any potential security risks or large files
        5. Prepare a comprehensive file analysis report

        Files to analyze: {len(files)}

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

    # Conditional Task 2: ADF Validation
    adf_files = [f for f in files if f.get("type") == "adf"]
    if adf_files:
        task_validate_adf = Task(
            description=f"""
            Validate {len(adf_files)} Azure Data Factory files against all checkpoints:

            CRITICAL Checkpoints (Must Pass):
            - Security Best Practices: No hardcoded credentials, use Key Vault/MSI
            - ADF Validation: Ensure all components pass ADF validation
            - Production Environment Readiness: Verify connectivity in production
            - Error Handling: Proper error handling and alert configuration

            HIGH Priority Checkpoints:
            - Naming Convention: Follow standard naming patterns
            - No Other Resources Impacted: Ensure isolated changes
            - Parameterization: Use global parameters for environment-specific values
            - Code Performance: Verify acceptable processing times
            - Test Coverage: All scenarios tested

            MEDIUM/LOW Priority Checkpoints:
            - Single Parent Pipeline Pattern
            - Component Reusability
            - Folder Organization
            - Logging Implementation

            For each checkpoint:
            1. Analyze the file content thoroughly
            2. Check against validation rules
            3. Document any violations with specific file and line references
            4. Provide actionable remediation suggestions

            Files to validate: {[f['path'] for f in adf_files]}
            """,
            expected_output="List of checkpoint results for ADF with pass/fail status and detailed suggestions",
            agent=agents["adf_specialist"]
        )
        tasks.append(task_validate_adf)

    # Conditional Task 3: Databricks Validation
    databricks_files = [f for f in files if f.get("type") == "databricks"]
    if databricks_files:
        task_validate_databricks = Task(
            description=f"""
            Validate {len(databricks_files)} Azure Databricks files against all checkpoints:

            CRITICAL Checkpoints (Must Pass):
            - Security Best Practices: No hardcoded secrets, use Secret Scope/Key Vault

            HIGH Priority Checkpoints:
            - Naming Conventions: Follow project standards
            - Code Performance: Optimize for Spark execution
            - Git Integration: Proper branching and PR workflow
            - Library Installations: Verify production cluster compatibility
            - Stress Testing: Handle production data volumes
            - Code Validation: Tested before check-in

            MEDIUM Priority Checkpoints:
            - Master-Child Notebook Pattern
            - Code Reusability
            - Logging Implementation
            - Documentation

            LOW Priority Checkpoints:
            - Folder Organization

            Performance Optimization Areas to Check:
            - Partitioning strategies
            - Broadcast join usage
            - Data shuffling minimization
            - Cluster configuration appropriateness

            For each checkpoint:
            1. Analyze notebook/code structure
            2. Identify violations with specific examples
            3. Suggest concrete improvements
            4. Consider Spark/Databricks best practices

            Files to validate: {[f['path'] for f in databricks_files]}
            """,
            expected_output="List of checkpoint results for Databricks with detailed performance suggestions",
            agent=agents["databricks_specialist"]
        )
        tasks.append(task_validate_databricks)

    # Conditional Task 4: SQL Validation
    sql_files = [f for f in files if f.get("type") == "sql"]
    if sql_files:
        task_validate_sql = Task(
            description=f"""
            Validate {len(sql_files)} Azure SQL files against all checkpoints:

            CRITICAL Checkpoints (Must Pass):
            - Access Control: Proper schema-level permissions

            HIGH Priority Checkpoints:
            - Use Constraints: Primary and foreign keys defined
            - Version Control: All SQL scripts in Git

            MEDIUM Priority Checkpoints:
            - Use Stored Procedures: Logic encapsulation
            - Use Schemas: Organized database structure
            - Naming Convention: Consistent naming standards
            - Data Types: Appropriate type selection
            - Logging: Implement in stored procedures

            LOW Priority Checkpoints:
            - Code Formatting: Consistent style

            For each checkpoint:
            1. Parse SQL statements and structure
            2. Verify best practices compliance
            3. Check for security vulnerabilities
            4. Suggest improvements for maintainability

            Files to validate: {[f['path'] for f in sql_files]}
            """,
            expected_output="List of checkpoint results for SQL with security and performance recommendations",
            agent=agents["sql_specialist"]
        )
        tasks.append(task_validate_sql)

    # Task 5: Generate Comprehensive Report
    task_generate_report = Task(
        description=f"""
        Generate a comprehensive validation report for PR {pr_id}:

        1. Compile all validation results from technology specialists
        2. Determine overall production readiness:
           - READY: No CRITICAL violations
           - NOT READY: One or more CRITICAL violations

        3. Create an executive summary that includes:
           - Overall status (ready/not ready)
           - Number of issues by severity
           - Technologies validated
           - Key risks or concerns

        4. Generate a prioritized remediation plan:
           - Group violations by severity (CRITICAL → HIGH → MEDIUM → LOW)
           - Provide specific, actionable steps for each violation
           - Estimate effort in hours for each severity level
           - Suggest order of fixes

        5. Format the report for both human reading and automated processing

        6. Include metrics:
           - Total checkpoints evaluated
           - Pass/fail ratio by technology
           - Estimated total remediation effort

        The report should be clear, actionable, and help developers quickly understand
        what needs to be fixed before the PR can be merged to production.
        """,
        expected_output="Complete PRValidationReport with status, violations, suggestions, and remediation plan",
        agent=agents["report_generator"],
        context=[task_analyze_pr] + [t for t in tasks if t != task_analyze_pr]  # Include all previous tasks as context
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
        {critical_issues}

        The plan should be immediately actionable by developers.
        """,
        expected_output="Detailed remediation plan with code examples and time estimates",
        agent=agents["report_generator"]
    )

    return task_remediation
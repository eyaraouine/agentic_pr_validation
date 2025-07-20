# src/crew/tasks.py - Version corrigée

from crewai import Task
from typing import List, Dict, Any
import json

from src.utils.logger import setup_logger

logger = setup_logger("crew.tasks")


def format_files_for_task(files: List[Dict[str, Any]]) -> str:
    """
    Format files data for task description
    Handles the JSON serialization properly to avoid issues with curly braces
    """
    # Create a simplified representation
    files_info = []
    for file in files:
        files_info.append({
            "path": file.get("path", ""),
            "type": file.get("type", "unknown"),
            "change_type": file.get("change_type", "add"),
            "has_content": bool(file.get("content", ""))
        })

    # Convert to formatted string
    return "\n".join([
        f"- Path: {f['path']}"
        f"\n  Type: {f['type']}"
        f"\n  Change: {f['change_type']}"
        f"\n  Content Available: {f['has_content']}"
        for f in files_info
    ])


# src/crew/tasks.py - Fixed version

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
    Create validation tasks for PR validation
    """
    tasks = []

    # Ensure files have proper structure
    files_with_content = []
    for file in files:
        file_data = {
            "path": file.get("path", ""),
            "type": file.get("type", "unknown"),
            "change_type": file.get("change_type", "add"),
            "content": file.get("content", "")
        }
        files_with_content.append(file_data)

    # Separate files by technology
    adf_files = [f for f in files_with_content if f.get("type") == "adf"]
    databricks_files = [f for f in files_with_content if f.get("type") == "databricks"]
    sql_files = [f for f in files_with_content if f.get("type") == "sql"]

    # Task 1: File Analysis
    task_analyze_pr = Task(
        description=f"""
Analyze pull request {pr_id} to understand the scope of changes.

Modified Files: {len(files)} files
- ADF files: {len(adf_files)}
- Databricks files: {len(databricks_files)}
- SQL files: {len(sql_files)}

Tasks to complete:
1. Review all modified files
2. Identify the technologies used
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

    # Task 2: ADF Validation
    if adf_files:
        # Store files data in task context instead of description
        task_validate_adf = Task(
            description=f"""
Validate {len(adf_files)} Azure Data Factory files.

Files to validate:
{chr(10).join('- ' + f["path"] for f in adf_files)}

Instructions:
1. Use check_adf_naming_convention tool to validate naming conventions
2. Use check_adf_security tool to check for security issues
3. Use check_adf_pipeline_pattern tool to verify pipeline patterns
4. Use check_adf_parameterization tool for parameterization
5. Use check_adf_validation tool for general validation
6. Use check_adf_error_handling tool for error handling

IMPORTANT: Pass the actual file data to each tool, not just the paths.
The files data is available in the task context.

Validate against all checkpoints:
CRITICAL: Security, ADF Validation, Production Readiness, Error Handling
HIGH: Naming Convention, No Impact, Parameterization, Performance, Testing
MEDIUM/LOW: Pipeline Pattern, Reusability, Folder Organization, Logging
""",
            expected_output="List of checkpoint results for ADF with pass/fail status",
            agent=agents["adf_specialist"],
            context=[task_analyze_pr],
            # Add files data to task context
            metadata={"files": adf_files}
        )
        tasks.append(task_validate_adf)

    # Task 3: Databricks Validation
    if databricks_files:
        task_validate_databricks = Task(
            description=f"""
Validate {len(databricks_files)} Azure Databricks files.

Files to validate:
{chr(10).join('- ' + f["path"] for f in databricks_files)}

Instructions:
1. Use check_databricks_naming tool for naming conventions
2. Use check_databricks_security tool for security practices
3. Use check_databricks_performance tool for performance
4. Use check_databricks_git_integration tool for Git practices
5. Use check_databricks_testing tool for test coverage
6. Use check_databricks_documentation tool for documentation

IMPORTANT: Pass the actual file data to each tool, not just the paths.
The files data is available in the task context.

Validate against all checkpoints:
CRITICAL: Security Best Practices
HIGH: Naming, Performance, Git Integration, Testing, Validation
MEDIUM/LOW: Pattern, Reusability, Logging, Documentation
""",
            expected_output="List of checkpoint results for Databricks",
            agent=agents["databricks_specialist"],
            context=[task_analyze_pr],
            metadata={"files": databricks_files}
        )
        tasks.append(task_validate_databricks)

    # Task 4: SQL Validation
    if sql_files:
        task_validate_sql = Task(
            description=f"""
Validate {len(sql_files)} Azure SQL files.

Files to validate:
{chr(10).join('- ' + f["path"] for f in sql_files)}

Instructions:
1. Use check_sql_stored_procedures tool for stored procedures
2. Use check_sql_constraints tool for PK/FK constraints
3. Use check_sql_schemas tool for schema organization
4. Use check_sql_naming_convention tool for naming standards
5. Use check_sql_security tool for security and access control
6. Use check_sql_version_control tool for version control

IMPORTANT: Pass the actual file data to each tool, not just the paths.
The files data is available in the task context.

Validate against all checkpoints:
CRITICAL: Access Control
HIGH: Constraints, Version Control
MEDIUM: Stored Procedures, Schemas, Naming, Data Types, Logging
LOW: Code Formatting
""",
            expected_output="List of checkpoint results for SQL",
            agent=agents["sql_specialist"],
            context=[task_analyze_pr],
            metadata={"files": sql_files}
        )
        tasks.append(task_validate_sql)

    # Task 5: Generate Report
    task_generate_report = Task(
        description=f"""
Generate a comprehensive validation report for PR {pr_id}.

Based on all validation results from the previous tasks:

1. Determine overall production readiness:
   - READY if no CRITICAL violations
   - NOT READY if any CRITICAL violations exist

2. Create executive summary with:
   - Total checkpoints evaluated
   - Pass/fail counts by severity
   - Key risks identified
   - Overall recommendation

3. Generate prioritized remediation plan:
   - Group issues by severity (CRITICAL, HIGH, MEDIUM, LOW)
   - Provide specific actions for each issue
   - Estimate effort in hours

4. Format report for clarity:
   - Use clear headings and sections
   - Include actionable next steps
   - Provide effort estimations

The report should include:
- Overall status (READY/NOT READY)
- Issues count by severity
- Technologies validated
- Specific remediation steps
- Total effort estimation
""",
        expected_output="Complete validation report with remediation plan",
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
    """
    critical_issues = [
        issue for issue in validation_report.get("checkpoint_results", [])
        if issue["status"] == "FAIL" and issue["severity"] == "CRITICAL"
    ]

    # Format critical issues for the task
    issues_summary = "\n".join([
        f"- {issue['technology']}: {issue['checkpoint_name']}"
        f"\n  Violations: {', '.join(issue.get('violations', []))}"
        for issue in critical_issues
    ])

    task_remediation = Task(
        description=f"""
Create a detailed remediation plan for PR {{pr_id}} with {len(critical_issues)} critical issues.

Critical Issues Found:
{issues_summary}

For each critical issue:
1. Analyze the root cause
2. Provide step-by-step fix instructions
3. Include code examples where applicable
4. Suggest preventive measures for future
5. Estimate time to fix (in hours)

Additional Requirements:
- Group related issues together
- Prioritize based on impact
- Consider dependencies between fixes
- Provide testing recommendations

The plan should be immediately actionable by developers.
""",
        expected_output="Detailed remediation plan with code examples and time estimates",
        agent=agents["report_generator"]
    )

    return task_remediation
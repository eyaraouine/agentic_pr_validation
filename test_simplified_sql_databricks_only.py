# test_simplified_analysis.py - Simplified version with direct result handling
from crewai import Crew, Agent, Task
import json
from src.tools.sql_tools import check_all_sql_compliance_tool
from src.tools.databricks_tools import check_all_databricks_compliance_tool
from src.config import get_llm_instance

# Define specialized agents
sql_analyst = Agent(
    role="SQL Standards Analyst",
    goal="Analyze SQL scripts and return structured JSON results",
    backstory="A database governance expert focused on SQL best practices.",
    verbose=True,
    llm=get_llm_instance(),
    tools=[check_all_sql_compliance_tool],
    max_iter=10
)

databricks_analyst = Agent(
    role="Databricks Standards Analyst",
    goal="Analyze Databricks notebooks and return structured JSON results",
    backstory="A Databricks expert specializing in notebook best practices.",
    verbose=True,
    llm=get_llm_instance(),
    tools=[check_all_databricks_compliance_tool],
    max_iter=10
)

# SQL Analysis Task
analyze_sql_task = Task(
    description=(
        """Analyze these SQL files:
{sql_files_info}

Run check_all_sql_compliance with format {{"files": {sql_files_json}}}

Return the complete JSON result."""
    ),
    expected_output="A JSON object with all SQL check results",
    agent=sql_analyst
)

# Databricks Analysis Task
analyze_databricks_task = Task(
    description=(
        """Analyze these Databricks files:
{databricks_files_info}

Run check_all_databricks_compliance with format {{"files": {databricks_files_json}}}

Return the complete JSON result."""
    ),
    expected_output="A JSON object with all Databricks check results",
    agent=databricks_analyst
)

# Create crew
crew = Crew(
    agents=[sql_analyst, databricks_analyst],
    tasks=[analyze_sql_task, analyze_databricks_task],
    verbose=True,
    process="sequential"
)


def generate_markdown_report(sql_results, databricks_results, sql_files, databricks_files):
    """Generate the final markdown report from the analysis results"""

    # Parse results if they're strings
    if isinstance(sql_results, str):
        try:
            sql_results = json.loads(sql_results) if sql_results.strip() else {}
        except json.JSONDecodeError:
            sql_results = {}

    if isinstance(databricks_results, str):
        try:
            databricks_results = json.loads(databricks_results) if databricks_results.strip() else {}
        except json.JSONDecodeError:
            databricks_results = {}

    # Count metrics
    sql_passed = sum(1 for check in sql_results.values() if check['status'] == 'PASS')
    sql_failed = sum(1 for check in sql_results.values() if check['status'] == 'FAIL')
    db_passed = sum(1 for check in databricks_results.values() if check['status'] == 'PASS')
    db_failed = sum(1 for check in databricks_results.values() if check['status'] == 'FAIL')

    # Collect violations by severity
    critical_issues = []
    high_issues = []
    medium_issues = []

    for check_name, check_data in sql_results.items():
        if check_data['status'] == 'FAIL':
            severity = check_data['severity']
            for i, violation in enumerate(check_data['violations']):
                issue = {
                    'technology': 'SQL',
                    'checkpoint': check_data['checkpoint'],
                    'violation': violation,
                    'suggestion': check_data['suggestions'][i] if i < len(check_data['suggestions']) else ''
                }
                if severity == 'CRITICAL':
                    critical_issues.append(issue)
                elif severity == 'HIGH':
                    high_issues.append(issue)
                elif severity == 'MEDIUM':
                    medium_issues.append(issue)

    for check_name, check_data in databricks_results.items():
        if check_data['status'] == 'FAIL':
            severity = check_data['severity']
            for i, violation in enumerate(check_data['violations']):
                issue = {
                    'technology': 'Databricks',
                    'checkpoint': check_data['checkpoint'],
                    'violation': violation,
                    'suggestion': check_data['suggestions'][i] if i < len(check_data['suggestions']) else ''
                }
                if severity == 'CRITICAL':
                    critical_issues.append(issue)
                elif severity == 'HIGH':
                    high_issues.append(issue)
                elif severity == 'MEDIUM':
                    medium_issues.append(issue)

    # Generate report
    report = f"""# Comprehensive Compliance Report

## Executive Summary

The compliance analysis was conducted on {len(sql_files)} SQL files and {len(databricks_files)} Databricks notebooks.

- **Total Checks**: {len(sql_results) + len(databricks_results)}
- **Passed**: {sql_passed + db_passed}
- **Failed**: {sql_failed + db_failed}

### Critical Findings

"""

    if critical_issues:
        for issue in critical_issues:
            report += f"- **{issue['technology']} - {issue['checkpoint']}**: {issue['violation']}\n"
    else:
        report += "- No critical violations found.\n"

    report += "\n---\n\n## SQL Compliance Section\n\n"

    if not sql_results:
        report += "⚠️ **Warning**: No SQL analysis results available.\n\n"
    else:
        report += "### Files Analyzed\n\n"
        for file in sql_files:
            report += f"- {file['path']}\n"

        report += "\n### Compliance Results\n\n"

        for check_name, check_data in sql_results.items():
            status_emoji = "✅" if check_data['status'] == 'PASS' else "❌"
            severity_color = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🟢", "LOW": "🔵"}.get(check_data['severity'], "")

            report += f"#### {status_emoji} {check_data['checkpoint']}\n"
            report += f"- **Status**: {check_data['status']}\n"
            report += f"- **Severity**: {severity_color} {check_data['severity']}\n"

            if check_data['violations']:
                report += f"- **Violations**:\n"
                for violation in check_data['violations']:
                    report += f"  - {violation}\n"

            if check_data['suggestions']:
                report += f"- **Suggestions**:\n"
                for suggestion in check_data['suggestions']:
                    report += f"  - {suggestion}\n"

            report += "\n"

        report += f"### Summary Metrics\n\n"
        report += f"- **Total Checks**: {len(sql_results)}\n"
        report += f"- **Passed**: {sql_passed}\n"
        report += f"- **Failed**: {sql_failed}\n"

    report += "\n---\n\n## Databricks Compliance Section\n\n"

    if not databricks_results:
        report += "⚠️ **Warning**: Databricks analysis failed to complete (agent timeout or error).\n\n"
        report += "Please re-run the analysis or check the Databricks notebooks manually.\n"
    else:
        report += "### Notebooks Analyzed\n\n"
        for file in databricks_files:
            report += f"- {file['path']}\n"

        report += "\n### Compliance Results\n\n"

        for check_name, check_data in databricks_results.items():
            status_emoji = "✅" if check_data['status'] == 'PASS' else "❌"
            severity_color = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🟢", "LOW": "🔵"}.get(check_data['severity'], "")

            report += f"#### {status_emoji} {check_data['checkpoint']}\n"
            report += f"- **Status**: {check_data['status']}\n"
            report += f"- **Severity**: {severity_color} {check_data['severity']}\n"

            if check_data['violations']:
                report += f"- **Violations**:\n"
                for violation in check_data['violations']:
                    report += f"  - {violation}\n"

            if check_data['suggestions']:
                report += f"- **Suggestions**:\n"
                for suggestion in check_data['suggestions']:
                    report += f"  - {suggestion}\n"

            report += "\n"

        report += f"### Summary Metrics\n\n"
        report += f"- **Total Checks**: {len(databricks_results)}\n"
        report += f"- **Passed**: {db_passed}\n"
        report += f"- **Failed**: {db_failed}\n"

    report += "\n---\n\n## Recommendations\n\n"

    if critical_issues:
        report += "### 🔴 CRITICAL (Immediate Action Required)\n\n"
        for issue in critical_issues:
            report += f"- **{issue['checkpoint']}**: {issue['suggestion']}\n"

    if high_issues:
        report += "\n### 🟡 HIGH (Within 1 Week)\n\n"
        for issue in high_issues:
            report += f"- **{issue['checkpoint']}**: {issue['suggestion']}\n"

    if medium_issues:
        report += "\n### 🟢 MEDIUM (Within 2 Weeks)\n\n"
        for issue in medium_issues:
            report += f"- **{issue['checkpoint']}**: {issue['suggestion']}\n"

    if not (critical_issues or high_issues or medium_issues):
        report += "No violations found. Continue following best practices and conduct regular audits.\n"

    return report


def generate_markdown_report2(sql_results, databricks_results, sql_files, databricks_files):
    """Generate the final markdown report from the analysis results"""

    # Parse results if they're strings
    if isinstance(sql_results, str):
        try:
            # Remove markdown code blocks if present
            sql_results = sql_results.strip()
            if sql_results.startswith("```json"):
                sql_results = sql_results[7:]  # Remove ```json
            if sql_results.endswith("```"):
                sql_results = sql_results[:-3]  # Remove ```
            sql_results = json.loads(sql_results.strip()) if sql_results.strip() else {}
        except json.JSONDecodeError:
            sql_results = {}

    if isinstance(databricks_results, str):
        try:
            # Remove markdown code blocks if present
            databricks_results = databricks_results.strip()
            if databricks_results.startswith("```json"):
                databricks_results = databricks_results[7:]  # Remove ```json
            if databricks_results.endswith("```"):
                databricks_results = databricks_results[:-3]  # Remove ```
            databricks_results = json.loads(databricks_results.strip()) if databricks_results.strip() else {}
        except json.JSONDecodeError:
            databricks_results = {}

    # Count metrics - DOIT ÊTRE ICI, PAS DANS LE EXCEPT
    sql_passed = sum(1 for check in sql_results.values() if isinstance(check, dict) and check.get('status') == 'PASS')
    sql_failed = sum(1 for check in sql_results.values() if isinstance(check, dict) and check.get('status') == 'FAIL')
    db_passed = sum(
        1 for check in databricks_results.values() if isinstance(check, dict) and check.get('status') == 'PASS')
    db_failed = sum(
        1 for check in databricks_results.values() if isinstance(check, dict) and check.get('status') == 'FAIL')

    # Collect violations by severity
    critical_issues = []
    high_issues = []
    medium_issues = []

    for check_name, check_data in sql_results.items():
        if isinstance(check_data, dict) and check_data.get('status') == 'FAIL':
            severity = check_data.get('severity', 'MEDIUM')
            violations = check_data.get('violations', [])
            suggestions = check_data.get('suggestions', [])

            for i, violation in enumerate(violations):
                issue = {
                    'technology': 'SQL',
                    'checkpoint': check_data.get('checkpoint', check_name),
                    'violation': violation,
                    'suggestion': suggestions[i] if i < len(suggestions) else ''
                }
                if severity == 'CRITICAL':
                    critical_issues.append(issue)
                elif severity == 'HIGH':
                    high_issues.append(issue)
                elif severity == 'MEDIUM':
                    medium_issues.append(issue)

    for check_name, check_data in databricks_results.items():
        if isinstance(check_data, dict) and check_data.get('status') == 'FAIL':
            severity = check_data.get('severity', 'MEDIUM')
            violations = check_data.get('violations', [])
            suggestions = check_data.get('suggestions', [])

            for i, violation in enumerate(violations):
                issue = {
                    'technology': 'Databricks',
                    'checkpoint': check_data.get('checkpoint', check_name),
                    'violation': violation,
                    'suggestion': suggestions[i] if i < len(suggestions) else ''
                }
                if severity == 'CRITICAL':
                    critical_issues.append(issue)
                elif severity == 'HIGH':
                    high_issues.append(issue)
                elif severity == 'MEDIUM':
                    medium_issues.append(issue)

    # Generate report
    report = f"""# Comprehensive Compliance Report

## Executive Summary

The compliance analysis was conducted on {len(sql_files)} SQL files and {len(databricks_files)} Databricks notebooks.

- **Total Checks**: {len(sql_results) + len(databricks_results)}
- **Passed**: {sql_passed + db_passed}
- **Failed**: {sql_failed + db_failed}

### Critical Findings

"""

    if critical_issues:
        for issue in critical_issues:
            report += f"- **{issue['technology']} - {issue['checkpoint']}**: {issue['violation']}\n"
    else:
        report += "- No critical violations found.\n"

    # SQL Section - only if SQL files exist
    if sql_files:
        report += "\n---\n\n## SQL Compliance Section\n\n"

        if not sql_results:
            report += "⚠️ **Warning**: No SQL analysis results available.\n\n"
        else:
            report += "### Files Analyzed\n\n"
            for file in sql_files:
                report += f"- {file['path']}\n"

            report += "\n### Compliance Results\n\n"

            for check_name, check_data in sql_results.items():
                if isinstance(check_data, dict):
                    status_emoji = "✅" if check_data.get('status') == 'PASS' else "❌"
                    severity = check_data.get('severity', 'MEDIUM')
                    severity_color = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🟢", "LOW": "🔵"}.get(severity, "")

                    report += f"#### {status_emoji} {check_data.get('checkpoint', check_name)}\n"
                    report += f"- **Status**: {check_data.get('status', 'UNKNOWN')}\n"
                    report += f"- **Severity**: {severity_color} {severity}\n"

                    violations = check_data.get('violations', [])
                    if violations:
                        report += f"- **Violations**:\n"
                        for violation in violations:
                            report += f"  - {violation}\n"

                    suggestions = check_data.get('suggestions', [])
                    if suggestions:
                        report += f"- **Suggestions**:\n"
                        for suggestion in suggestions:
                            report += f"  - {suggestion}\n"

                    report += "\n"

            report += f"### Summary Metrics\n\n"
            report += f"- **Total Checks**: {len(sql_results)}\n"
            report += f"- **Passed**: {sql_passed}\n"
            report += f"- **Failed**: {sql_failed}\n"

    # Databricks Section - only if Databricks files exist
    if databricks_files:
        report += "\n---\n\n## Databricks Compliance Section\n\n"

        if not databricks_results:
            report += "⚠️ **Warning**: Databricks analysis failed to complete (agent timeout or error).\n\n"
            report += "Please re-run the analysis or check the Databricks notebooks manually.\n"
        else:
            report += "### Notebooks Analyzed\n\n"
            for file in databricks_files:
                report += f"- {file['path']}\n"

            report += "\n### Compliance Results\n\n"

            for check_name, check_data in databricks_results.items():
                if isinstance(check_data, dict):
                    status_emoji = "✅" if check_data.get('status') == 'PASS' else "❌"
                    severity = check_data.get('severity', 'MEDIUM')
                    severity_color = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🟢", "LOW": "🔵"}.get(severity, "")

                    report += f"#### {status_emoji} {check_data.get('checkpoint', check_name)}\n"
                    report += f"- **Status**: {check_data.get('status', 'UNKNOWN')}\n"
                    report += f"- **Severity**: {severity_color} {severity}\n"

                    violations = check_data.get('violations', [])
                    if violations:
                        report += f"- **Violations**:\n"
                        for violation in violations:
                            report += f"  - {violation}\n"

                    suggestions = check_data.get('suggestions', [])
                    if suggestions:
                        report += f"- **Suggestions**:\n"
                        for suggestion in suggestions:
                            report += f"  - {suggestion}\n"

                    report += "\n"

            report += f"### Summary Metrics\n\n"
            report += f"- **Total Checks**: {len(databricks_results)}\n"
            report += f"- **Passed**: {db_passed}\n"
            report += f"- **Failed**: {db_failed}\n"

    # Recommendations
    report += "\n---\n\n## Recommendations\n\n"

    if critical_issues:
        report += "### 🔴 CRITICAL (Immediate Action Required)\n\n"
        for issue in critical_issues:
            report += f"- **{issue['checkpoint']}**: {issue['suggestion']}\n"

    if high_issues:
        report += "\n### 🟡 HIGH (Within 1 Week)\n\n"
        for issue in high_issues:
            report += f"- **{issue['checkpoint']}**: {issue['suggestion']}\n"

    if medium_issues:
        report += "\n### 🟢 MEDIUM (Within 2 Weeks)\n\n"
        for issue in medium_issues:
            report += f"- **{issue['checkpoint']}**: {issue['suggestion']}\n"

    if not (critical_issues or high_issues or medium_issues):
        report += "No violations found. Continue following best practices and conduct regular audits.\n"

    return report


def identify_file_type(file_path: str, content: str) -> str:
    """Identify if a file is SQL or Databricks based on path and content"""
    if file_path.endswith('.sql'):
        return 'sql'
    elif file_path.endswith(('.py', '.ipynb')):
        return 'databricks'

    sql_patterns = ['CREATE TABLE', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'ALTER TABLE']
    databricks_patterns = ['spark.', 'dbutils.', 'dataframe', 'pyspark', '# COMMAND ----------']

    content_upper = content.upper()
    sql_count = sum(1 for pattern in sql_patterns if pattern in content_upper)

    content_lower = content.lower()
    databricks_count = sum(1 for pattern in databricks_patterns if pattern in content_lower)

    return 'sql' if sql_count > databricks_count else 'databricks'


if __name__ == "__main__":
    # Files to check
    files_to_check = [
        {
            "path": "create_customer_table.sql",
            "content": """
                CREATE TABLE Customer (
                    ID INT,
                    Name VARCHAR(100),
                    Email VARCHAR(255)
                );
            """
        },
        {
            "path": "sql/tables/create_customer_table_v2.sql",
            "content": """-- =============================================
-- Author:      Data Team
-- Create date: 2024-01-15
-- Description: Create customer table with proper constraints
-- Version:     1.0.0
-- =============================================

-- Create schema if not exists
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'dbo')
BEGIN
    EXEC('CREATE SCHEMA dbo')
END
GO

-- Create customer table
CREATE TABLE dbo.Customer (
    CustomerID INT IDENTITY(1,1) NOT NULL,
    CustomerCode NVARCHAR(20) NOT NULL,
    FirstName NVARCHAR(100) NOT NULL,
    LastName NVARCHAR(100) NOT NULL,
    Email NVARCHAR(255) NOT NULL,
    Phone NVARCHAR(20) NULL,
    DateOfBirth DATE NULL,
    IsActive BIT NOT NULL DEFAULT 1,
    CreatedDate DATETIME2(7) NOT NULL DEFAULT SYSDATETIME(),
    CreatedBy NVARCHAR(100) NOT NULL DEFAULT SYSTEM_USER,
    ModifiedDate DATETIME2(7) NOT NULL DEFAULT SYSDATETIME(),
    ModifiedBy NVARCHAR(100) NOT NULL DEFAULT SYSTEM_USER,
    RowVersion ROWVERSION NOT NULL,

    CONSTRAINT PK_Customer PRIMARY KEY CLUSTERED (CustomerID),
    CONSTRAINT UQ_Customer_Code UNIQUE (CustomerCode),
    CONSTRAINT UQ_Customer_Email UNIQUE (Email),
    CONSTRAINT CK_Customer_Email CHECK (Email LIKE '%_@_%._%'),
    CONSTRAINT CK_Customer_Phone CHECK (Phone IS NULL OR Phone LIKE '+%' OR Phone LIKE '[0-9]%')
)
GO

-- Create indexes
CREATE NONCLUSTERED INDEX IX_Customer_Email ON dbo.Customer(Email)
GO

-- Grant permissions
GRANT SELECT ON dbo.Customer TO [DataReaderRole]
GO
"""
        },
        {
            "path": "notebooks/data_processing.py",
            "content": """# Databricks notebook source
# COMMAND ----------

# Data Processing Notebook
# Author: Data Engineering Team
# Created: 2024-01-20
# Version: 1.0

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, avg, count

# Initialize Spark session
spark = SparkSession.builder.appName("DataProcessing").getOrCreate()

# COMMAND ----------

# Read data from Delta Lake
df_customers = spark.read.format("delta").load("/mnt/datalake/customers")

# Basic data validation
print(f"Total customers: {df_customers.count()}")
df_customers.printSchema()

# COMMAND ----------

# Data transformation without proper error handling
df_transformed = df_customers \
    .filter(col("IsActive") == True) \
    .groupBy("Country") \
    .agg(
        count("CustomerID").alias("customer_count"),
        avg("TotalPurchases").alias("avg_purchases")
    )

# This should use display() instead
df_transformed.show()

# COMMAND ----------

# Save results - missing partitioning
df_transformed.write \
    .mode("overwrite") \
    .format("delta") \
    .save("/mnt/datalake/customer_analytics")
"""
        },
        {
            "path": "notebooks/ETL_Pipeline.py",
            "content": """# Databricks notebook source
# COMMAND ----------

# ETL Pipeline for Customer Data

import pyspark.sql.functions as F
from delta import DeltaTable

# Hardcoded connection string - security issue
connection_string = "Server=myserver.database.windows.net;Database=mydb;User=admin;Password=MyP@ssw0rd123"

# COMMAND ----------

# Read source data
df_source = spark.read \
    .format("jdbc") \
    .option("url", f"jdbc:sqlserver://{connection_string}") \
    .option("dbtable", "raw_customers") \
    .option("password", "MyP@ssw0rd123") \
    .load()

# No error handling here
df_transformed = df_source.select("*").filter(F.col("created_date") >= "2024-01-01")

# Using collect without limit - performance issue
all_records = df_transformed.collect()
print(f"Processing {len(all_records)} records")

# COMMAND ----------

# Complex join without broadcast hint
df_orders = spark.read.format("delta").load("/mnt/datalake/orders")

df_final = df_transformed.join(
    df_orders,
    df_transformed.customer_id == df_orders.customer_id,
    "left"
)

# Multiple operations without caching
df_final.filter(F.col("order_amount") > 100).count()
df_final.filter(F.col("order_status") == "completed").count()

# COMMAND ----------

# TODO: Add data quality checks
# FIXME: Performance is slow on large datasets

# Debug code left in
print("debug: transformation complete")

# Write without optimization
df_final.repartition(1).write.format("parquet").save("/output/customers")
"""
        }
    ]

    # Separate files by type
    sql_files = []
    databricks_files = []

    for file in files_to_check:
        file_type = identify_file_type(file['path'], file['content'])
        if file_type == 'sql':
            sql_files.append(file)
        else:
            databricks_files.append(file)

    print(f"Identified {len(sql_files)} SQL files and {len(databricks_files)} Databricks files")


    # Prepare data for all cases
    if sql_files :
        sql_files_info = "\n".join([
            f"File: {f['path']}\nContent:\n{f['content']}\n"
            for f in sql_files
        ])
        sql_files_json = json.dumps(sql_files)

    if databricks_files :
        databricks_files_info = "\n".join([
        f"File: {f['path']}\nContent:\n{f['content']}\n"
        for f in databricks_files
    ])
        databricks_files_json = json.dumps(databricks_files)


    # Build tasks list dynamically
    tasks = []
    agents = []

    if sql_files:
        tasks.append(analyze_sql_task)
        agents.append(sql_analyst)

    if databricks_files:
        tasks.append(analyze_databricks_task)
        agents.append(databricks_analyst)

    # Create crew only if we have tasks
    if tasks:
        crew = Crew(
            agents=agents,  # Only include needed agents
            tasks=tasks,
            verbose=True,
            process="sequential"
        )
        # Build inputs dynamically
        inputs = {}

        if sql_files:
            inputs["sql_files_info"] = "\n".join([
                f"File: {f['path']}\nContent:\n{f['content']}\n"
                for f in sql_files
            ])
            inputs["sql_files_json"] = json.dumps(sql_files)


        if databricks_files:
            inputs["databricks_files_info"] = "\n".join([
                f"File: {f['path']}\nContent:\n{f['content']}\n"
                for f in databricks_files
            ])
            inputs["databricks_files_json"] = json.dumps(databricks_files)

        # Run analysis
        results = crew.kickoff(inputs=inputs)


        # Extract results
        sql_results = "{}"
        databricks_results = "{}"

        task_index = 0
        if sql_files:
            sql_results = crew.tasks[task_index].output.raw_output
            print("=" * 100)
            print(f"Results for sql: {sql_results}")
            print("=" * 100)
            task_index += 1

        if databricks_files:
            databricks_results = crew.tasks[task_index].output.raw_output
            print("=" * 100)
            print(f"Results for databricks: {databricks_results}")
            print("=" * 100)
        else:
            print("No files to analyze!")
            sql_results = "{}"
            databricks_results = "{}"

        # Generate final report
        final_report = generate_markdown_report2(
            sql_results,
            databricks_results,
            sql_files,
            databricks_files
        )

        print("=" * 100)
        print("FINAL COMPLIANCE REPORT:")
        print("=" * 100)
        print(final_report)


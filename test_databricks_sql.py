# test_parallel_analysis.py
from crewai import Crew, Agent, Task
import json
from src.tools.sql_tools import (
    check_sql_constraints_tool,
    check_sql_schemas_tool,
    check_sql_stored_procedures_tool,
    check_sql_naming_convention_tool,
    check_sql_security_tool,
    check_sql_version_control_tool
)
from src.tools.databricks_tools import (
    check_databricks_naming_tool,
    check_databricks_security_tool,
    check_databricks_performance_tool,
    check_databricks_git_integration_tool,
    check_databricks_testing_tool,
    check_databricks_documentation_tool
)
from src.config import get_llm_instance

# Define the SQL Analyst Agent
sql_analyst = Agent(
    role="SQL Standards Analyst",
    goal="Analyze SQL scripts to ensure compliance with organizational best practices",
    backstory="A database governance expert focused on maintainability, security, and performance.",
    verbose=True,
    llm=get_llm_instance(),
    tools=[
        check_sql_constraints_tool,
        check_sql_schemas_tool,
        check_sql_stored_procedures_tool,
        check_sql_naming_convention_tool,
        check_sql_security_tool,
        check_sql_version_control_tool
    ],
    max_iter=15  # Increased for better completion
)

# Define the Databricks Analyst Agent
databricks_analyst = Agent(
    role="Databricks Standards Analyst",
    goal="Analyze Databricks notebooks to ensure compliance with best practices for performance, security, and maintainability",
    backstory="A Databricks expert specializing in Spark optimization, notebook development standards, and cloud data engineering best practices.",
    verbose=True,
    llm=get_llm_instance(),
    tools=[
        check_databricks_naming_tool,
        check_databricks_security_tool,
        check_databricks_performance_tool,
        check_databricks_git_integration_tool,
        check_databricks_testing_tool,
        check_databricks_documentation_tool
    ],
    max_iter=15  # Increased for better completion
)

# Define the Report Generator Agent
report_writer = Agent(
    role="Compliance Report Specialist",
    goal="Generate comprehensive compliance reports organized by technology (SQL and Databricks) with clear violations, severity levels, and actionable recommendations",
    backstory="An expert in synthesizing technical compliance data from multiple sources into executive-level insights and actionable recommendations.",
    verbose=True,
    llm=get_llm_instance(),
    max_iter=10,
    allow_delegation=False  # Prevent delegation to other agents
)

# SQL Analysis Task - Improved with clearer structure
analyze_sql_task = Task(
    description=(
        """Analyze the provided SQL files for compliance with best practices.

        SQL files to analyze:
        {sql_files_info}

        IMPORTANT: Apply each of these checks EXACTLY ONCE and compile ALL results:
        1. check_sql_constraints - Check for proper PRIMARY KEY and NOT NULL constraints
        2. check_sql_schemas - Check for proper schema organization
        3. check_sql_naming_convention - Check naming conventions
        4. check_sql_security - Check security best practices
        5. check_sql_version_control - Check version control practices
        6. check_sql_stored_procedures - Check stored procedure standards (if applicable)

        Use this exact format for all tools:
        {{"files": {sql_files_json}}}

        DO NOT repeat the same check multiple times.
        After running all checks, compile the results into a single JSON response."""
    ),
    expected_output=(
        """A complete JSON dictionary with ALL check results in this exact format:
        {{
            "check_sql_constraints": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_sql_schemas": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_sql_naming_convention": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_sql_security": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_sql_version_control": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }}
        }}"""
    ),
    agent=sql_analyst
)

# Databricks Analysis Task - Improved with clearer structure
analyze_databricks_task = Task(
    description=(
        """Analyze the provided Databricks notebooks for compliance with best practices.

        Databricks files to analyze:
        {databricks_files_info}

        IMPORTANT: Apply each of these checks EXACTLY ONCE and compile ALL results:
        1. check_databricks_naming - Check notebook naming conventions
        2. check_databricks_security - Check security best practices (hardcoded credentials, etc.)
        3. check_databricks_performance - Check performance optimizations
        4. check_databricks_git_integration - Check Git integration and practices
        5. check_databricks_testing - Check testing coverage
        6. check_databricks_documentation - Check code documentation

        Use this exact format for all tools:
        {{"files": {databricks_files_json}}}

        DO NOT repeat the same check multiple times.
        After running all checks, compile the results into a single JSON response."""
    ),
    expected_output=(
        """A complete JSON dictionary with ALL check results in this exact format:
        {{
            "check_databricks_naming": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_databricks_security": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_databricks_performance": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_databricks_git_integration": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_databricks_testing": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }},
            "check_databricks_documentation": {{ "checkpoint": "...", "status": "...", "violations": [...], "suggestions": [...], "severity": "..." }}
        }}"""
    ),
    agent=databricks_analyst
)

# Combined Report Task - Simplified to avoid re-asking for data
report_task = Task(
    description=(
        """You have received the compliance analysis results from both SQL and Databricks analysts.

        Using ONLY the data provided in the context (do NOT ask for more data), create a comprehensive Markdown report that includes:

        1. **Executive Summary**: 
           - Overall compliance status
           - Number of passed/failed checks per technology
           - Critical findings that need immediate attention

        2. **SQL Compliance Section**:
           - List of SQL files analyzed
           - Detailed table with all checkpoints, their status, severity, violations, and suggestions
           - Summary metrics (total checks, passed, failed, by severity)

        3. **Databricks Compliance Section**:
           - List of Databricks notebooks analyzed
           - Detailed table with all checkpoints, their status, severity, violations, and suggestions
           - Summary metrics (total checks, passed, failed, by severity)

        4. **Recommendations**: 
           - Prioritized list of actions based on severity (CRITICAL → HIGH → MEDIUM → LOW)
           - Specific remediation steps for each violation
           - Timeline suggestions for fixes

        Format the report with:
        - Clear markdown headers and subheaders
        - Well-formatted tables
        - Bullet points for readability
        - Bold text for emphasis on critical items"""
    ),
    expected_output="A comprehensive compliance report in Markdown format with all sections properly formatted and data accurately represented from the analysis results.",
    agent=report_writer,
    context=[analyze_sql_task, analyze_databricks_task]
)

# Crew configuration with sequential processing to ensure order
crew = Crew(
    agents=[sql_analyst, databricks_analyst, report_writer],
    tasks=[analyze_sql_task, analyze_databricks_task, report_task],
    verbose=True,
    process="sequential"  # Ensures tasks complete in order
)


def identify_file_type(file_path: str, content: str) -> str:
    """Identify if a file is SQL or Databricks based on path and content"""
    # Check file extension
    if file_path.endswith('.sql'):
        return 'sql'
    elif file_path.endswith(('.py', '.ipynb')):
        return 'databricks'

    # Check content patterns
    sql_patterns = ['CREATE TABLE', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'ALTER TABLE']
    databricks_patterns = ['spark.', 'dbutils.', 'dataframe', 'pyspark', '# COMMAND ----------']

    content_upper = content.upper()
    sql_count = sum(1 for pattern in sql_patterns if pattern in content_upper)

    content_lower = content.lower()
    databricks_count = sum(1 for pattern in databricks_patterns if pattern in content_lower)

    if sql_count > databricks_count:
        return 'sql'
    elif databricks_count > 0:
        return 'databricks'
    else:
        # Default based on common patterns
        return 'sql' if sql_count > 0 else 'databricks'


if __name__ == "__main__":
    # Files to check - mixing SQL and Databricks files
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

    # Prepare SQL files info
    sql_files_info = "\n".join([
        f"File: {f['path']}\nContent:\n{f['content']}\n"
        for f in sql_files
    ]) if sql_files else "No SQL files to analyze"

    # Prepare Databricks files info
    databricks_files_info = "\n".join([
        f"File: {f['path']}\nContent:\n{f['content']}\n"
        for f in databricks_files
    ]) if databricks_files else "No Databricks files to analyze"

    # JSON format for tools
    sql_files_json = json.dumps(sql_files) if sql_files else "[]"
    databricks_files_json = json.dumps(databricks_files) if databricks_files else "[]"

    # Launch analysis with prepared files
    result = crew.kickoff(inputs={
        "sql_files_info": sql_files_info,
        "sql_files_json": sql_files_json,
        "databricks_files_info": databricks_files_info,
        "databricks_files_json": databricks_files_json
    })

    print("=" * 100)
    print("FINAL COMPLIANCE REPORT:")
    print("=" * 100)
    print(result)
# test_simple_fixed.py
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
    max_iter=10  # Limiter les itérations pour éviter les boucles
)

# Define the Report Generator Agent
report_writer = Agent(
    role="SQL Compliance Reporter",
    goal="Generate a clear, structured compliance report with violations, severity, and suggestions",
    backstory="An expert in summarizing technical audit data into actionable and executive-level insights.",
    verbose=True,
    llm=get_llm_instance()
)

# Tâche d'analyse mise à jour
analyze_task = Task(
    description=(
        """Analyze the provided SQL files for compliance with best practices.

        You have been provided with the following SQL files to analyze:
        {files_info}

        For each file, determine which checks are relevant based on the content and apply the appropriate tools.

        Use the tools with the exact file data provided above. Do NOT use placeholder filenames like 'file1.sql'.

        The tools expect input in this format:
        {{"files": {files_json}}}

        Apply relevant checks and produce a structured report."""
    ),
    expected_output=(
        "A JSON-style dictionary containing results for each check (tool) with keys: "
        "{{ tool_name: {{ checkpoint, status, violations, suggestions, severity }} }}"
    ),
    agent=sql_analyst
)

# Report task reste la même
report_task = Task(
    description=(
        "You will receive the JSON output from the SQL standards analyst. "
        "Use it to write a Markdown report that includes: each checkpoint name, its status, severity, "
        "the violations found, and the suggestions. Format the report clearly."
    ),
    expected_output="A complete compliance report in Markdown format with proper structure.",
    agent=report_writer,
    context=[analyze_task]
)

# Crew configuration
crew = Crew(
    agents=[sql_analyst, report_writer],
    tasks=[analyze_task, report_task],
    verbose=True
)

if __name__ == "__main__":
    # Fichiers à vérifier
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
        }
    ]

    # Préparer les informations des fichiers pour l'agent
    files_info = "\n".join([
        f"File: {f['path']}\nContent:\n{f['content']}\n"
        for f in files_to_check
    ])

    # JSON des fichiers pour les outils
    files_json = json.dumps(files_to_check)

    # Lancer l'analyse avec les fichiers préparés
    result = crew.kickoff(inputs={
        "files_info": files_info,
        "files_json": files_json
    })

    print("==========================================================================================================")
    print("RÉSULTAT FINAL:")

    print(result)
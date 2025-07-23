import os

# IMPORTANT: Désactiver complètement OpenTelemetry AVANT tout import de crewai
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = ""
os.environ["OTEL_TRACES_EXPORTER"] = "none"
os.environ["OTEL_METRICS_EXPORTER"] = "none"
os.environ["OTEL_LOGS_EXPORTER"] = "none"

# Désactiver spécifiquement la télémétrie CrewAI
os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

# Maintenant on peut importer les modules
from crewai import Crew, Agent, Task
import json
from src.tools.sql_tools import check_all_sql_compliance_tool
from src.tools.databricks_tools import check_all_databricks_compliance_tool
from src.tools.adf_tools import check_all_adf_compliance_tool
from src.config import get_llm_instance

import socket
socket.setdefaulttimeout(1)

# Agents
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

adf_analyst = Agent(
    role="ADF Standards Analyst",
    goal="Analyze Azure Data Factory pipelines and return structured JSON results",
    backstory="An Azure Data Factory specialist ensuring pipeline design best practices.",
    verbose=True,
    llm=get_llm_instance(),
    tools=[check_all_adf_compliance_tool],
    max_iter=10
)

# Tasks
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

analyze_adf_task = Task(
    description=(
        """Analyze these ADF pipeline files:
{adf_files_info}

Run check_all_adf_compliance with format {{"files": {adf_files_json}}}

Return the complete JSON result."""
    ),
    expected_output="A JSON object with all ADF check results",
    agent=adf_analyst
)


def identify_file_type(file_path: str, content: str) -> str:
    """Identifie le type de fichier basé sur l'extension et le contenu."""
    # Vérification par extension d'abord
    if file_path.endswith('.sql'):
        return 'sql'
    elif file_path.endswith(('.py', '.ipynb')):
        return 'databricks'
    elif file_path.endswith('.json'):
        # Amélioration de la détection des fichiers ADF
        # Vérifier les différents types de ressources ADF
        adf_patterns = [
            '"activities"',  # Pipelines
            '"type": "Microsoft.DataFactory/factories/pipelines"',
            '"type": "Microsoft.DataFactory/factories/linkedservices"',
            '"type": "Microsoft.DataFactory/factories/datasets"',
            '"type": "Microsoft.DataFactory/factories/dataflows"',
            '"type": "Microsoft.DataFactory/factories/triggers"',
            '"linkedServiceName"',  # Datasets
            '"typeProperties"',  # Commun aux ressources ADF
            '"referenceName"',  # Références ADF
            '"pipelineReference"',
            '"datasetReference"',
            '"dataflowReference"'
        ]

        # Vérifier aussi le chemin du fichier pour les indices ADF
        adf_path_patterns = ['adf/', 'pipeline', 'linkedservice', 'dataset', 'dataflow', 'trigger']

        # Vérifier si c'est un fichier ADF
        for pattern in adf_patterns:
            if pattern in content:
                return 'adf'

        # Vérifier le chemin
        path_lower = file_path.lower()
        for pattern in adf_path_patterns:
            if pattern in path_lower:
                return 'adf'

    # Détection basée sur le contenu pour les fichiers sans extension claire
    sql_patterns = ['CREATE TABLE', 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'ALTER TABLE', 'CREATE VIEW',
                    'CREATE PROCEDURE']
    databricks_patterns = ['spark.', 'dbutils.', 'dataframe', 'pyspark', '# COMMAND ----------', 'DataFrame',
                           'SparkSession']

    content_upper = content.upper()
    content_lower = content.lower()

    # Compter les patterns SQL vs Databricks
    sql_count = sum(p in content_upper for p in sql_patterns)
    databricks_count = sum(p in content_lower for p in databricks_patterns)

    if sql_count > databricks_count:
        return 'sql'
    elif databricks_count > 0:
        return 'databricks'

    # Par défaut, si c'est un JSON non identifié, considérer comme ADF
    if file_path.endswith('.json'):
        return 'adf'

    # Sinon, par défaut databricks
    return 'databricks'


def generate_markdown_report2(sql_results, databricks_results, adf_results, sql_files, databricks_files, adf_files):
    """Génère un rapport Markdown consolidé avec violations et suggestions associées."""

    def parse_json_result(results):
        if isinstance(results, dict):
            return results
        if isinstance(results, str):
            try:
                cleaned = results.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                if cleaned and not cleaned.endswith('}'):
                    last_brace = cleaned.rfind('}')
                    if last_brace > 0:
                        open_count = cleaned[:last_brace + 1].count('{')
                        close_count = cleaned[:last_brace + 1].count('}')
                        while close_count < open_count:
                            cleaned = cleaned[:last_brace + 1] + '}'
                            close_count += 1
                            last_brace += 1

                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}")
                return {}
        return results or {}

    # Parse results
    sql_results = parse_json_result(sql_results)
    databricks_results = parse_json_result(databricks_results)
    adf_results = parse_json_result(adf_results)

    # Count passed/failed
    def count_results(results):
        if not isinstance(results, dict):
            return 0, 0
        passed = failed = 0
        for check in results.values():
            if isinstance(check, dict):
                status = check.get('status', '').upper()
                if status == 'PASS':
                    passed += 1
                elif status == 'FAIL':
                    failed += 1
        return passed, failed

    sql_passed, sql_failed = count_results(sql_results)
    db_passed, db_failed = count_results(databricks_results)
    adf_passed, adf_failed = count_results(adf_results)

    # Collect issues
    critical_issues, high_issues, medium_issues = [], [], []

    def collect_issues(results, tech_name):
        if not isinstance(results, dict):
            return
        for check_name, check_data in results.items():
            if isinstance(check_data, dict) and check_data.get('status') == 'FAIL':
                severity = check_data.get('severity', 'MEDIUM')
                violations = check_data.get('violations', [])
                ai_suggestions = check_data.get('ai_suggestions', [])
                generic_suggestions = check_data.get('suggestions', [])

                for i, violation in enumerate(violations):
                    ai_suggestion = ai_suggestions[i] if i < len(ai_suggestions) else ""
                    generic_suggestion = generic_suggestions[i] if i < len(generic_suggestions) else ""

                    issue = {
                        'technology': tech_name,
                        'checkpoint': check_data.get('checkpoint', check_name),
                        'violation': violation,
                        'ai_suggestion': ai_suggestion,
                        'generic_suggestion': generic_suggestion
                    }

                    if severity == 'CRITICAL':
                        critical_issues.append(issue)
                    elif severity == 'HIGH':
                        high_issues.append(issue)
                    elif severity == 'MEDIUM':
                        medium_issues.append(issue)

    collect_issues(sql_results, "SQL")
    collect_issues(databricks_results, "Databricks")
    collect_issues(adf_results, "ADF")

    report = f"""# Comprehensive Compliance Report

## Executive Summary

Analysis conducted on {len(sql_files)} SQL files, {len(databricks_files)} Databricks files, and {len(adf_files)} ADF files.

- **Total Checks**: {len(sql_results) + len(databricks_results) + len(adf_results)}
- **Passed**: {sql_passed + db_passed + adf_passed}
- **Failed**: {sql_failed + db_failed + adf_failed}

### Critical Findings

"""

    if critical_issues:
        for issue in critical_issues:
            report += f"- **{issue['technology']} - {issue['checkpoint']}**: {issue['violation']}\n"
    else:
        report += "- No critical violations found.\n"

    def add_section(title, files, results):
        nonlocal report
        if files:
            report += f"\n---\n\n## {title} Compliance Section\n\n"

            has_valid_results = (
                    isinstance(results, dict) and
                    results and
                    any(isinstance(v, dict) for v in results.values())
            )

            if not has_valid_results:
                report += f"⚠️ **Warning**: {title} analysis failed or returned no results.\n\n"
            else:
                report += "### Files Analyzed\n\n"
                for file in files:
                    report += f"- {file['path']}\n"

                report += "\n### Compliance Results\n\n"
                for check_name, check_data in results.items():
                    if isinstance(check_data, dict):
                        status_emoji = "✅" if check_data.get('status') == 'PASS' else "❌"
                        severity = check_data.get('severity', 'MEDIUM')
                        severity_color = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "🟢", "LOW": "🔵"}.get(severity, "")

                        report += f"#### {status_emoji} {check_data.get('checkpoint', check_name)}\n"
                        report += f"- **Status**: {check_data.get('status', 'UNKNOWN')}\n"
                        report += f"- **Severity**: {severity_color} {severity}\n\n"

                        violations = check_data.get('violations', [])
                        ai_suggestions = check_data.get('ai_suggestions', [])
                        generic_suggestions = check_data.get('suggestions', [])

                        if violations:
                            report += "**Issues Found:**\n\n"
                            for i, violation in enumerate(violations):
                                report += f"**Issue {i + 1}:**\n"
                                report += f"- 🚨 **Problem**: {violation}\n"

                                if i < len(generic_suggestions):
                                    report += f"- 💡 **Quick Fix**: {generic_suggestions[i]}\n"

                                if i < len(ai_suggestions):
                                    ai_suggestion = ai_suggestions[i]


                                    # Formatter le code correctement
                                    if '```' in ai_suggestion:
                                        # Séparer le texte et le code
                                        parts = ai_suggestion.split('```')
                                        formatted_suggestion = ""
                                        for j, part in enumerate(parts):
                                            if j % 2 == 0:  # Texte normal
                                                formatted_suggestion += part
                                            else:  # Code
                                                # Extraire le langage et le code
                                                lines = part.split('\n', 1)
                                                if len(lines) > 1:
                                                    lang = lines[0]
                                                    code = lines[1]
                                                    formatted_suggestion += f"\n\n```{lang}\n{code}\n```\n\n"
                                                else:
                                                    formatted_suggestion += f"\n\n```\n{part}\n```\n\n"
                                    else:
                                        formatted_suggestion = ai_suggestion

                                    report += f"- 🤖 **Detailed Solution**: {formatted_suggestion}\n"

                                report += "\n"

                        report += "---\n\n"

                passed = sum(1 for c in results.values() if isinstance(c, dict) and c.get('status') == 'PASS')
                failed = sum(1 for c in results.values() if isinstance(c, dict) and c.get('status') == 'FAIL')

                report += f"### Summary Metrics\n\n"
                report += f"- **Total Checks**: {len(results)}\n"
                report += f"- **Passed**: {passed}\n"
                report += f"- **Failed**: {failed}\n"

    add_section("SQL", sql_files, sql_results)
    add_section("Databricks", databricks_files, databricks_results)
    add_section("ADF", adf_files, adf_results)

    # Action Items
    report += "\n---\n\n## Action Items\n\n"

    def add_recommendations(issues, priority_name, priority_emoji):
        nonlocal report
        if issues:
            report += f"### {priority_emoji} {priority_name} Priority\n\n"
            for i, issue in enumerate(issues, 1):
                report += f"**{i}. {issue['technology']} - {issue['checkpoint']}**\n\n"
                report += f"**Issue**: {issue['violation']}\n\n"

                if issue['ai_suggestion']:
                    ai_suggestion = issue['ai_suggestion']


                    # Formatter le code correctement
                    if '```' in ai_suggestion:
                        parts = ai_suggestion.split('```')
                        formatted_suggestion = ""
                        for j, part in enumerate(parts):
                            if j % 2 == 0:  # Texte normal
                                formatted_suggestion += part
                            else:  # Code
                                lines = part.split('\n', 1)
                                if len(lines) > 1:
                                    lang = lines[0]
                                    code = lines[1]
                                    formatted_suggestion += f"\n\n```{lang}\n{code}\n```\n\n"
                                else:
                                    formatted_suggestion += f"\n\n```\n{part}\n```\n\n"
                    else:
                        formatted_suggestion = ai_suggestion

                    report += f"**Solution**: {formatted_suggestion}\n\n"
                elif issue['generic_suggestion']:
                    report += f"**Solution**: {issue['generic_suggestion']}\n\n"

                report += "---\n\n"

    add_recommendations(critical_issues, "CRITICAL (Immediate Action)", "🔴")
    add_recommendations(high_issues, "HIGH (Within 1 Week)", "🟡")
    add_recommendations(medium_issues, "MEDIUM (Within 2 Weeks)", "🟢")

    if not (critical_issues or high_issues or medium_issues):
        report += "✅ **Excellent!** No violations found. Continue following best practices.\n"

    return report

def main():
    """Fonction principale pour exécuter l'analyse de conformité."""
    # Files to check
    files_to_check = [
        # Fichiers SQL existants
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

        # Fichiers Databricks existants
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
        },

        # NOUVEAUX FICHIERS ADF
        {
            "path": "adf/pipelines/MasterOrchestrator.json",
            "content": json.dumps({
                "name": "MasterOrchestrator",  # Mauvais nom - devrait être master_orchestrator_pipeline
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            "name": "Execute Customer Pipeline",
                            "type": "ExecutePipeline",
                            "typeProperties": {
                                "pipeline": {
                                    "referenceName": "ProcessCustomerData",
                                    "type": "PipelineReference"
                                }
                            },
                            "dependsOn": []
                        },
                        {
                            "name": "Execute Order Pipeline",
                            "type": "ExecutePipeline",
                            "typeProperties": {
                                "pipeline": {
                                    "referenceName": "ProcessOrderData",
                                    "type": "PipelineReference"
                                }
                            },
                            "dependsOn": [
                                {
                                    "activity": "Execute Customer Pipeline",
                                    "dependencyConditions": ["Succeeded"]
                                }
                            ]
                        }
                    ]
                }
            })
        },
        {
            "path": "adf/pipelines/process_customer_data_pipeline.json",
            "content": json.dumps({
                "name": "process_customer_data_pipeline",
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            "name": "Copy Customer Data",
                            "type": "Copy",
                            "typeProperties": {
                                "source": {
                                    "type": "SqlServerSource",
                                    "sqlReaderQuery": "SELECT * FROM dev.dbo.Customers"  # Environnement hardcodé
                                },
                                "sink": {
                                    "type": "AzureSqlSink"
                                }
                            },
                            "policy": {
                                "timeout": "7.00:00:00"
                                # Manque retry policy
                            }
                        }
                    ]
                }
            })
        },
        {
            "path": "adf/linkedservices/AzureSqlDatabase_ls.json",
            "content": json.dumps({
                "name": "AzureSqlDatabase_ls",
                "type": "Microsoft.DataFactory/factories/linkedservices",
                "properties": {
                    "type": "AzureSqlDatabase",
                    "typeProperties": {
                        "connectionString": "Server=tcp:myserver.database.windows.net,1433;Database=mydb;User ID=admin;Password=MySecretPass123!;",
                        # Password hardcodé
                        "authenticationType": "SQL"  # Pas MSI ou Key Vault
                    }
                }
            })
        },
        {
            "path": "adf/linkedservices/azure_blob_storage_ls.json",
            "content": json.dumps({
                "name": "azure_blob_storage_ls",
                "type": "Microsoft.DataFactory/factories/linkedservices",
                "properties": {
                    "type": "AzureBlobStorage",
                    "typeProperties": {
                        "sasUri": "https://mystorageaccount.blob.core.windows.net/?sv=2020-08-04&ss=bfqt&srt=sco&sp=rwdlacupx&se=2024-12-31T23:59:59Z&st=2024-01-01T00:00:00Z&spr=https&sig=XXXXX"
                        # SAS token hardcodé
                    }
                }
            })
        },
        {
            "path": "adf/datasets/CustomerDataset.json",  # Mauvais nom - devrait être customer_dataset
            "content": json.dumps({
                "name": "CustomerDataset",
                "type": "Microsoft.DataFactory/factories/datasets",
                "properties": {
                    "linkedServiceName": {
                        "referenceName": "AzureSqlDatabase_ls",
                        "type": "LinkedServiceReference"
                    },
                    "type": "AzureSqlTable",
                    "typeProperties": {
                        "tableName": "dbo.Customers"
                    }
                }
            })
        },
        {
            "path": "adf/pipelines/data_quality_pipeline.json",
            "content": json.dumps({
                "name": "data_quality_pipeline",
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "parameters": {
                        "SourceTable": {
                            "type": "string",
                            "defaultValue": "Customers"
                        }
                    },
                    "activities": [
                        {
                            "name": "Check Data Quality",
                            "type": "DataFlow",
                            "typeProperties": {
                                "dataflow": {
                                    "referenceName": "DataQualityFlow",
                                    "type": "DataFlowReference"
                                }
                            },
                            "policy": {
                                "retry": 2,
                                "retryIntervalInSeconds": 30
                            }
                        },
                        {
                            "name": "Send Failure Alert",
                            "type": "Web",
                            "typeProperties": {
                                "url": "@pipeline().globalParameters.AlertEmailEndpoint",
                                "method": "POST",
                                "body": {
                                    "subject": "Data Quality Check Failed",
                                    "message": "@{activity('Check Data Quality').error.message}"
                                }
                            },
                            "dependsOn": [
                                {
                                    "activity": "Check Data Quality",
                                    "dependencyConditions": ["Failed"]
                                }
                            ]
                        }
                    ]
                }
            })
        },
        {
            "path": "adf/pipelines/invalid_pipeline.json",
            "content": json.dumps({
                # JSON invalide - manque "name" et "type"
                "properties": {
                    "activities": []
                }
            })
        },
        {
            "path": "adf/dataflows/customer_transform_dataflow.json",
            "content": json.dumps({
                "name": "customer_transform_dataflow",
                "type": "Microsoft.DataFactory/factories/dataflows",
                "properties": {
                    "type": "MappingDataFlow",
                    "typeProperties": {
                        "sources": [
                            {
                                "name": "CustomerSource",
                                "dataset": {
                                    "referenceName": "CustomerDataset",
                                    "type": "DatasetReference"
                                }
                            }
                        ]
                    }
                }
            })
        },
        {
            "path": "adf/triggers/daily_etl_trigger.json",
            "content": json.dumps({
                "name": "daily_etl_trigger",
                "type": "Microsoft.DataFactory/factories/triggers",
                "properties": {
                    "type": "ScheduleTrigger",
                    "typeProperties": {
                        "recurrence": {
                            "frequency": "Day",
                            "interval": 1,
                            "startTime": "2024-01-01T02:00:00Z",
                            "timeZone": "UTC"
                        }
                    },
                    "pipelines": [
                        {
                            "pipelineReference": {
                                "referenceName": "MasterOrchestrator",
                                "type": "PipelineReference"
                            }
                        }
                    ]
                }
            })
        },
        {
            "path": "adf/pipelines/very_long_name_that_exceeds_the_maximum_allowed_characters_for_azure_data_factory_pipeline_names_which_should_be_under_140_characters_pipeline.json",
            "content": json.dumps({
                "name": "very_long_name_that_exceeds_the_maximum_allowed_characters_for_azure_data_factory_pipeline_names_which_should_be_under_140_characters_pipeline",
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            # Activité sans nom
                            "type": "Copy"
                        }
                    ]
                }
            })
        },
        {
            "path": "adf/pipelines/individual_table_pipeline_01.json",
            "content": json.dumps({
                "name": "process_customers_table",
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            "name": "Copy Customers",
                            "type": "Copy",
                            "typeProperties": {}
                        }
                    ]
                }
            })
        },
        {
            "path": "adf/pipelines/individual_table_pipeline_02.json",
            "content": json.dumps({
                "name": "process_orders_table",
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            "name": "Copy Orders",
                            "type": "Copy",
                            "typeProperties": {}
                        }
                    ]
                }
            })
        },
        {
            "path": "adf/pipelines/individual_table_pipeline_03.json",
            "content": json.dumps({
                "name": "process_products_table",
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            "name": "Copy Products",
                            "type": "Copy",
                            "typeProperties": {}
                        }
                    ]
                }
            })
        },
        {
            "path": "adf/pipelines/individual_table_pipeline_04.json",
            "content": json.dumps({
                "name": "process_inventory_table",
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            "name": "Copy Inventory",
                            "type": "Copy",
                            "typeProperties": {}
                        }
                    ]
                }
            })
        }
    ]

    sql_files, databricks_files, adf_files = [], [], []

    for file in files_to_check:
        file_type = identify_file_type(file['path'], file['content'])
        if file_type == 'sql':
            sql_files.append(file)
        elif file_type == 'databricks':
            databricks_files.append(file)
        elif file_type == 'adf':
            adf_files.append(file)

    tasks, agents, inputs = [], [], {}

    if sql_files:
        tasks.append(analyze_sql_task)
        agents.append(sql_analyst)
        inputs["sql_files_info"] = "\n".join([f"File: {f['path']}\nContent:\n{f['content']}\n" for f in sql_files])
        inputs["sql_files_json"] = json.dumps(sql_files)

    if databricks_files:
        tasks.append(analyze_databricks_task)
        agents.append(databricks_analyst)
        inputs["databricks_files_info"] = "\n".join(
            [f"File: {f['path']}\nContent:\n{f['content']}\n" for f in databricks_files])
        inputs["databricks_files_json"] = json.dumps(databricks_files)

    if adf_files:
        tasks.append(analyze_adf_task)
        agents.append(adf_analyst)
        inputs["adf_files_info"] = "\n".join([f"File: {f['path']}\nContent:\n{f['content']}\n" for f in adf_files])
        inputs["adf_files_json"] = json.dumps(adf_files)

    if tasks:
        try:
            crew = Crew(agents=agents, tasks=tasks, verbose=True, process="sequential")
            results = crew.kickoff(inputs=inputs)

            sql_results = "{}"
            databricks_results = "{}"
            adf_results = "{}"

            task_index = 0
            if sql_files:
                sql_results = crew.tasks[task_index].output.raw_output
                task_index += 1
                print("==========SQL RESULTS===========", sql_results)
            if databricks_files:
                databricks_results = crew.tasks[task_index].output.raw_output
                task_index += 1
                print("============Databricks RESULTS=========", databricks_results)
            if adf_files:
                adf_results = crew.tasks[task_index].output.raw_output
                print("============ADF RESULTS===========", adf_results)

            final_report = generate_markdown_report2(sql_results, databricks_results, adf_results, sql_files,
                                                     databricks_files, adf_files)
            print("\n" + "=" * 100)
            print("FINAL COMPLIANCE REPORT:")
            print("=" * 100 + "\n")
            print(final_report)

        except Exception as e:
            print(f"Une erreur s'est produite lors de l'exécution: {e}")
            raise
    else:
        print("No valid files provided for analysis.")


if __name__ == "__main__":
    main()
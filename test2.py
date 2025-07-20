#!/usr/bin/env python3
"""
Script de test amélioré pour le système de validation PR
Teste avec du contenu réel dans les fichiers
"""

import requests
import json
from datetime import datetime
import time
import sys

# Configuration
API_URL = "http://127.0.0.1:8080/api/v1/validate"
API_KEY = "9GfA2kB7ZtNqX8YwL6C1D0VpJrM4EiUsTbVxRcQyWzHuLfKgNpOmBeXtAz"  # Remplacer par votre clé API

# Headers avec infos Azure DevOps optionnelles
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
    # Ces headers sont optionnels pour le mode test
    # "X-Azure-DevOps-Org": "https://dev.azure.com/testorg",
    # "X-Project": "TestProject",
    # "X-Repository": "TestRepo"
}

# Données de test avec contenu réel
test_pr_data = {
    "pr_id": f"TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    "source_branch": "feature/add-customer-pipeline",
    "target_branch": "main",
    "title": "Add new customer data pipeline",
    "description": "This PR adds a new ADF pipeline for processing customer data",
    "created_by": "dev.user@company.com",
    "files": [
        {
            "path": "datafactory/pipelines/customer_data_pipeline.json",
            "change_type": "add",
            "content": json.dumps({
                "name": "customer_data_pipeline",
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            "name": "CopyCustomerData",
                            "type": "Copy",
                            "dependsOn": [],
                            "policy": {
                                "timeout": "7.00:00:00",
                                "retry": 2,
                                "retryIntervalInSeconds": 30,
                                "secureOutput": False,
                                "secureInput": False
                            },
                            "userProperties": [],
                            "typeProperties": {
                                "source": {
                                    "type": "AzureSqlSource",
                                    "sqlReaderQuery": "@{pipeline().parameters.sourceQuery}",
                                    "queryTimeout": "02:00:00",
                                    "partitionOption": "None"
                                },
                                "sink": {
                                    "type": "ParquetSink",
                                    "storeSettings": {
                                        "type": "AzureBlobFSWriteSettings"
                                    },
                                    "formatSettings": {
                                        "type": "ParquetWriteSettings"
                                    }
                                },
                                "enableStaging": False,
                                "translator": {
                                    "type": "TabularTranslator",
                                    "typeConversion": True,
                                    "typeConversionSettings": {
                                        "allowDataTruncation": True,
                                        "treatBooleanAsNumber": False
                                    }
                                }
                            },
                            "inputs": [{
                                "referenceName": "SourceDataset",
                                "type": "DatasetReference"
                            }],
                            "outputs": [{
                                "referenceName": "SinkDataset",
                                "type": "DatasetReference"
                            }],
                            "linkedServiceName": {
                                "referenceName": "AzureSqlDatabase_ls",
                                "type": "LinkedServiceReference"
                            }
                        },
                        {
                            "name": "SendFailureEmail",
                            "type": "Web",
                            "dependsOn": [{
                                "activity": "CopyCustomerData",
                                "dependencyConditions": ["Failed"]
                            }],
                            "policy": {
                                "timeout": "7.00:00:00",
                                "retry": 0,
                                "retryIntervalInSeconds": 30,
                                "secureOutput": False,
                                "secureInput": False
                            },
                            "userProperties": [],
                            "typeProperties": {
                                "url": "@pipeline().parameters.emailWebhookUrl",
                                "method": "POST",
                                "body": {
                                    "message": "Pipeline failed",
                                    "pipeline": "@pipeline().Pipeline",
                                    "error": "@activity('CopyCustomerData').error"
                                }
                            }
                        }
                    ],
                    "parameters": {
                        "sourceQuery": {
                            "type": "String",
                            "defaultValue": "SELECT * FROM customers WHERE modified_date >= '@{formatDateTime(adddays(utcnow(),-1),'yyyy-MM-dd')}'"
                        },
                        "emailWebhookUrl": {
                            "type": "String"
                        }
                    },
                    "annotations": [],
                    "lastPublishTime": "2024-01-15T10:30:00Z"
                }
            }, indent=2)
        },
        {
            "path": "databricks/notebooks/process_customer_data.py",
            "change_type": "add",
            "content": """# Databricks notebook source
# MAGIC %md
# MAGIC # Customer Data Processing Notebook
# MAGIC 
# MAGIC This notebook processes customer data from the data lake
# MAGIC 
# MAGIC **Author:** Data Team  
# MAGIC **Created:** 2024-01-15  
# MAGIC **Version:** 1.0.0

# COMMAND ----------

# Import required libraries
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, lit, current_timestamp
from pyspark.sql.types import *
import logging
from datetime import datetime

# COMMAND ----------

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# COMMAND ----------

# Get parameters from job
dbutils.widgets.text("input_path", "/mnt/raw/customers", "Input Path")
dbutils.widgets.text("output_path", "/mnt/processed/customers", "Output Path")
dbutils.widgets.text("processing_date", "", "Processing Date")

input_path = dbutils.widgets.get("input_path")
output_path = dbutils.widgets.get("output_path")
processing_date = dbutils.widgets.get("processing_date") or datetime.now().strftime("%Y-%m-%d")

logger.info(f"Processing data for date: {processing_date}")

# COMMAND ----------

def validate_data(df):
    \"\"\"Validate customer data quality\"\"\"
    # Check for nulls in required fields
    null_counts = df.select(
        [count(when(col(c).isNull(), c)).alias(c) for c in df.columns]
    ).collect()[0].asDict()

    # Log validation results
    for col_name, null_count in null_counts.items():
        if null_count > 0:
            logger.warning(f"Column {col_name} has {null_count} null values")

    # Check row count
    row_count = df.count()
    logger.info(f"Total rows: {row_count}")

    if row_count == 0:
        raise ValueError("No data found to process")

    return df

# COMMAND ----------

# Main processing logic
try:
    # Read data
    logger.info(f"Reading data from {input_path}")
    df = spark.read.parquet(input_path)

    # Validate data
    df = validate_data(df)

    # Apply transformations
    df_transformed = df \\
        .filter(col("active") == True) \\
        .withColumn("processing_timestamp", current_timestamp()) \\
        .withColumn("processing_date", lit(processing_date))

    # Cache for performance
    df_transformed.cache()

    # Write results
    logger.info(f"Writing results to {output_path}")
    df_transformed.write \\
        .mode("overwrite") \\
        .partitionBy("processing_date") \\
        .parquet(output_path)

    # Log success metrics
    logger.info(f"Successfully processed {df_transformed.count()} records")

except Exception as e:
    logger.error(f"Processing failed: {str(e)}")
    raise

# COMMAND ----------

# Cleanup
spark.catalog.clearCache()
"""
        },
        {
            "path": "sql/tables/create_customer_table.sql",
            "change_type": "add",
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

-- Drop table if exists
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'Customer' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    DROP TABLE dbo.Customer
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

    -- Constraints
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

CREATE NONCLUSTERED INDEX IX_Customer_LastName_FirstName ON dbo.Customer(LastName, FirstName)
GO

-- Add extended properties
EXEC sys.sp_addextendedproperty 
    @name=N'Description', 
    @value=N'Stores customer master data', 
    @level0type=N'SCHEMA',
    @level0name=N'dbo', 
    @level1type=N'TABLE',
    @level1name=N'Customer'
GO

-- Grant permissions (example - adjust based on your security model)
-- GRANT SELECT ON dbo.Customer TO [DataReaderRole]
-- GRANT INSERT, UPDATE, DELETE ON dbo.Customer TO [DataWriterRole]
-- GO
"""
        }
    ],
    "repository": {
        "id": "test-repo-123",
        "name": "data-platform",
        "url": "https://dev.azure.com/testorg/TestProject/_git/data-platform"
    }
}


def print_section(title: str, char: str = "="):
    """Print a formatted section header"""
    print(f"\n{char * 80}")
    print(f" {title}")
    print(f"{char * 80}")


def test_health_check():
    """Test API health endpoint"""
    try:
        response = requests.get(f"{API_URL.replace('/v1/validate', '/health')}")
        if response.status_code == 200:
            print("✅ API is healthy")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {str(e)}")
        return False


def test_validation():
    """Run the validation test"""
    print_section("🚀 PR VALIDATION TEST", "=")

    print(f"\n📋 Test Details:")
    print(f"   PR ID: {test_pr_data['pr_id']}")
    print(f"   Files: {len(test_pr_data['files'])} files")
    print(f"   - ADF Pipeline: customer_data_pipeline.json")
    print(f"   - Databricks Notebook: process_customer_data.py")
    print(f"   - SQL Script: create_customer_table.sql")

    # Check API health first
    print("\n🏥 Checking API health...")
    if not test_health_check():
        print("\n💡 Please ensure the API is running:")
        print("   uvicorn api.main:app --port 8080")
        return

    try:
        # Send validation request
        print("\n📤 Sending validation request...")
        start_time = time.time()

        response = requests.post(
            API_URL,
            headers=headers,
            json=test_pr_data,
            timeout=300
        )

        elapsed_time = time.time() - start_time
        print(f"⏱️  Response received in {elapsed_time:.2f} seconds")
        print(f"📊 Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            print_section("✨ VALIDATION RESULTS", "-")

            # Overall Status
            print(f"\n🎯 Overall Status:")
            status_icon = "✅" if result['production_ready'] else "❌"
            print(f"   Production Ready: {status_icon} {'YES' if result['production_ready'] else 'NO'}")
            print(f"   Summary: {result.get('overall_summary', 'N/A')}")

            # Technologies
            print(f"\n🔧 Technologies Detected: {len(result.get('technologies_detected', []))}")
            for tech in result.get('technologies_detected', []):
                print(f"   • {tech}")

            # Issues Summary
            print(f"\n📊 Validation Summary:")
            critical = result.get('critical_issues_count', 0)
            total_checkpoints = len(result.get('checkpoint_results', []))
            passed = sum(1 for cp in result.get('checkpoint_results', []) if cp['status'] == 'PASS')

            print(f"   Total Checkpoints: {total_checkpoints}")
            print(f"   Passed: {passed}")
            print(f"   Failed: {total_checkpoints - passed}")
            print(f"   Critical Issues: {critical}")

            # Checkpoint Details by Technology
            print(f"\n🔍 Checkpoint Results:")
            tech_results = {}
            for checkpoint in result.get('checkpoint_results', []):
                tech = checkpoint.get('technology', 'Unknown')
                if tech not in tech_results:
                    tech_results[tech] = []
                tech_results[tech].append(checkpoint)

            for tech, checkpoints in tech_results.items():
                print(f"\n   📁 {tech}:")
                for cp in checkpoints[:5]:  # Show first 5
                    status_icon = "✅" if cp['status'] == "PASS" else "❌"
                    print(f"      {status_icon} {cp['checkpoint_name']} [{cp['severity']}]")

                    if cp.get('violations'):
                        print(f"         Violations: {len(cp['violations'])}")
                        for v in cp['violations'][:2]:
                            print(f"         • {v[:80]}...")

                if len(checkpoints) > 5:
                    print(f"      ... and {len(checkpoints) - 5} more checkpoints")

            # Remediation Plan
            if result.get('remediation_plan'):
                plan = result['remediation_plan']
                print_section("🔧 REMEDIATION PLAN", "-")

                total_effort = sum(plan.get('estimated_effort', {}).values())
                if total_effort > 0:
                    print(f"\n⏱️  Estimated Effort: {total_effort:.1f} hours ({total_effort / 8:.1f} days)")

                if plan.get('immediate_actions'):
                    print(f"\n🚨 Immediate Actions: {len(plan['immediate_actions'])}")
                if plan.get('high_priority_actions'):
                    print(f"⚠️  High Priority: {len(plan['high_priority_actions'])}")

            # Save report
            report_file = f"validation_report_{test_pr_data['pr_id']}.json"
            with open(report_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n💾 Full report saved: {report_file}")

        else:
            print(f"\n❌ Validation failed with status {response.status_code}")
            error_detail = response.json() if response.headers.get(
                'content-type') == 'application/json' else response.text
            print(
                f"Error: {json.dumps(error_detail, indent=2) if isinstance(error_detail, dict) else error_detail[:500]}")

    except requests.exceptions.Timeout:
        print("\n⏱️  Request timed out after 5 minutes")
        print("💡 The validation might still be running. Check the API logs.")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API")
        print("💡 Please ensure the API is running on port 8080")

    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 80)
    print(" 🧪 PR VALIDATION SYSTEM - TEST SUITE")
    print("=" * 80)

    print("\n⚙️  Configuration:")
    print(f"   API URL: {API_URL}")
    print(f"   Mode: Test with embedded file content")

    print("\n💡 Tips:")
    print("   - Make sure the API is running: uvicorn api.main:app --port 8080")
    print("   - Check that your API key matches the one in .env")
    print("   - This test includes actual file content, no Azure DevOps needed")

    print("\n" + "-" * 80)
    input("Press ENTER to start test...")

    test_validation()

    print("\n✅ Test completed!")
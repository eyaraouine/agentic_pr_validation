#!/usr/bin/env python3
"""
Enhanced test script for PR validation with CrewAI
Works without requiring actual Azure DevOps connection
"""

import requests
import json
from datetime import datetime
import time

# Configuration
API_URL = "http://127.0.0.1:8080/api/v1/validate"
API_KEY = "9GfA2kB7ZtNqX8YwL6C1D0VpJrM4EiUsTbVxRcQyWzHuLfKgNpOmBeXtAz"

# Headers - Using fake Azure DevOps info for testing
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
    "X-Azure-DevOps-Org": "https://dev.azure.com/testorg",
    "X-Project": "TestProject",
    "X-Repository": "TestRepo"
}

# Test PR with properly structured data
test_pr_data = {
    "pr_id": f"TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    "source_branch": "feature/add-new-pipeline",
    "target_branch": "main",
    "title": "Add new customer data pipeline with security issues",
    "description": "This PR adds a new ADF pipeline for processing customer data with Databricks transformations",
    "created_by": "test.user@company.com",
    "files": [
        # ADF file with multiple issues
        {
            "path": "datafactory/pipelines/customer_pipeline.json",
            "change_type": "add",
            "type": "adf",
            "content": json.dumps({
                "name": "CustomerDataPipeline",  # Bad name (should end with _pipeline)
                "type": "Microsoft.DataFactory/factories/pipelines",
                "properties": {
                    "activities": [
                        {
                            "name": "CopyCustomerData",
                            "type": "Copy",
                            "linkedServiceName": {
                                "referenceName": "AzureSqlDatabase",
                                "type": "LinkedServiceReference"
                            },
                            "typeProperties": {
                                "source": {
                                    "type": "SqlSource",
                                    # CRITICAL: Hardcoded connection string
                                    "connectionString": "Server=tcp:myserver.database.windows.net;Database=mydb;User ID=admin;Password=MyP@ssw0rd123!;"
                                },
                                "sink": {
                                    "type": "BlobSink"
                                }
                            },
                            # Missing retry policy
                            "policy": {}
                        }
                    ],
                    # No parameters for environment-specific values
                    "parameters": {}
                }
            }, indent=2)
        },
        # Databricks notebook with issues
        {
            "path": "databricks/notebooks/process_customer_data.py",
            "change_type": "add",
            "type": "databricks",
            "content": """# Process Customer Data Notebook
# Missing header documentation

import pyspark.sql.functions as F
from pyspark.sql import SparkSession

# TODO: Fix this later (no assignee)
# CRITICAL: Hardcoded credentials
password = "admin123"
api_key = "sk-1234567890abcdef"

# Initialize Spark
spark = SparkSession.builder.appName("CustomerProcessing").getOrCreate()

# Read data without error handling
df = spark.read.parquet("/mnt/raw/customers")

# Inefficient filtering - should cache
result = df.filter(F.col("active") == True).filter(F.col("country") == "US").filter(F.col("age") > 18)

# No partitioning strategy
result.write.mode("overwrite").parquet("/mnt/processed/us_customers")

# Debug print that shouldn't be in production
print(f"Processing complete with password: {password}")

# Missing: No tests, no data validation, no error handling
"""
        },
        # SQL file with issues
        {
            "path": "sql/tables/create_customer_table.sql",
            "change_type": "add",
            "type": "sql",
            "content": """-- Create customer table
-- Missing version info and author

CREATE TABLE customers (
    id INT,  -- No PRIMARY KEY
    name VARCHAR(100),
    email VARCHAR(100),
    password VARCHAR(50),  -- Storing passwords in plain text!
    created_date DATETIME
);
-- Missing constraints, indexes, and permissions

-- Direct data access without stored procedure
SELECT * FROM customers WHERE password = 'admin123';

-- No error handling or transaction management
INSERT INTO customers VALUES (1, 'Test', 'test@test.com', 'password123', GETDATE());
"""
        }
    ],
    "repository": {
        "id": "test-repo-123",
        "name": "TestRepo",
        "url": "https://dev.azure.com/testorg/TestProject/_git/TestRepo"
    }
}


def test_validation():
    """Run the enhanced PR validation test"""
    print("🚀 Starting Enhanced PR Validation Test...")
    print(f"   PR ID: {test_pr_data['pr_id']}")
    print(f"   Files: {len(test_pr_data['files'])}")
    print(f"   Expected Issues: Multiple CRITICAL security issues")
    print()

    try:
        # Send the request
        print("📤 Sending validation request...")
        start_time = time.time()

        response = requests.post(
            API_URL,
            headers=headers,
            json=test_pr_data,
            timeout=300  # 5 minutes timeout
        )

        elapsed_time = time.time() - start_time
        print(f"⏱️  Response received in {elapsed_time:.2f} seconds")
        print(f"📊 Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            print("\n" + "=" * 80)
            print(" 🎯 VALIDATION RESULTS")
            print("=" * 80)

            # Overall Status
            print(f"\n📋 Overall Status:")
            print(f"   Production Ready: {'✅ YES' if result['production_ready'] else '❌ NO'}")
            print(f"   Overall Summary: {result.get('overall_summary', 'N/A')}")

            # Technologies
            print(f"\n🔧 Technologies Detected:")
            for tech in result.get('technologies_detected', []):
                print(f"   - {tech}")

            # Issues Summary
            print(f"\n⚠️  Issues Summary:")
            print(f"   Critical Issues: {result.get('critical_issues_count', 0)}")
            print(f"   Total Checkpoints: {len(result.get('checkpoint_results', []))}")

            # Detailed Checkpoint Results
            print(f"\n📊 Checkpoint Results by Technology:")

            # Group by technology
            tech_results = {}
            for checkpoint in result.get('checkpoint_results', []):
                tech = checkpoint.get('technology', 'Unknown')
                if tech not in tech_results:
                    tech_results[tech] = []
                tech_results[tech].append(checkpoint)

            for tech, checkpoints in tech_results.items():
                print(f"\n   🔹 {tech}:")
                for cp in checkpoints:
                    status_icon = "✅" if cp['status'] == "PASS" else "❌"
                    print(f"      {status_icon} {cp['checkpoint_name']} [{cp['severity']}]")

                    if cp['violations']:
                        print("         Violations:")
                        for v in cp['violations'][:3]:  # Show first 3
                            print(f"         • {v[:100]}...")
                        if len(cp['violations']) > 3:
                            print(f"         • ... and {len(cp['violations']) - 3} more")

            # Remediation Plan
            if result.get('remediation_plan'):
                plan = result['remediation_plan']
                print(f"\n🔧 Remediation Plan:")

                if plan.get('immediate_actions'):
                    print(f"   🚨 Immediate Actions Required: {len(plan['immediate_actions'])}")

                effort = plan.get('estimated_effort', {})
                total_hours = sum(effort.values())
                print(f"   ⏱️  Total Effort: {total_hours:.1f} hours")
                print(f"   📅 Estimated Days: {total_hours / 8:.1f} days")

            # Save detailed report
            report_file = f"validation_report_{test_pr_data['pr_id']}.json"
            with open(report_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n💾 Detailed report saved: {report_file}")

            # Test Success Criteria
            print("\n" + "=" * 80)
            print(" ✅ TEST VALIDATION")
            print("=" * 80)

            expected_issues = [
                ("Hardcoded credentials in ADF", result['critical_issues_count'] > 0),
                ("Password in Databricks", any('password' in str(cp.get('violations', [])).lower()
                                               for cp in result.get('checkpoint_results', []))),
                ("SQL security issues", any('sql' in cp.get('technology', '').lower()
                                            for cp in result.get('checkpoint_results', [])))
            ]

            for issue, found in expected_issues:
                print(f"   {'✅' if found else '❌'} {issue}: {'Found' if found else 'Not Found'}")

        else:
            print(f"\n❌ Error {response.status_code}")
            print(f"Response: {response.text[:500]}...")

            if response.status_code == 422:
                print("\n💡 Validation Error - Check request format")
            elif response.status_code == 500:
                print("\n💡 Server Error - Check logs for details")

    except requests.exceptions.Timeout:
        print("⏱️  Request timed out after 5 minutes")
        print("💡 Consider increasing timeout for large validations")

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API")
        print("💡 Ensure API is running: uvicorn api.main:app --reload")

    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 80)
    print(" 🧪 ENHANCED PR VALIDATION TEST")
    print("=" * 80)

    print("\n⚙️  Test Configuration:")
    print(f"   API URL: {API_URL}")
    print(f"   Test includes: 3 files with multiple security issues")
    print(f"   Expected result: NOT production ready")

    print("\n" + "-" * 80)
    input("Press ENTER to start validation test...")

    test_validation()
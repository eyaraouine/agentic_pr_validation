#!/usr/bin/env python3
"""
Simple test to trigger a PR validation with CrewAI
"""

import requests
import json
from datetime import datetime

# Configuration
API_URL = "http://127.0.0.1:8000/api/v1/validate"
API_KEY = "9GfA2kB7ZtNqX8YwL6C1D0VpJrM4EiUsTbVxRcQyWzHuLfKgNpOmBeXtAz"  # Replace with your API_KEY from the .env file

# Required headers
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
    "X-Azure-DevOps-Org": "sdxcloud",
    "X-Project": "Datahub_LLM_Ops",
    "X-Repository": "SpendAnalytics"
}

# Example PR with different file types
test_pr_data = {
    "pr_id": f"TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    "source_branch": "feature/add-new-pipeline",
    "target_branch": "main",
    "title": "Add new customer data pipeline",
    "description": "This PR adds a new ADF pipeline for processing customer data with Databricks transformations",
    "created_by": "eya@sodexo.com",
    "files": [
        # ADF file with security issue
        {
            "path": "datafactory/pipelines/customer_pipeline.json",
            "change_type": "add",
            "content": json.dumps({
                "name": "CustomerDataPipeline",  # Incorrect name (should end with _pipeline)
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
                                    "connectionString": "Server=tcp:myserver.database.windows.net;Database=mydb;User ID=admin;Password=MyP@ssw0rd123!;"
                                    # Security issue!
                                }
                            }
                        }
                    ],
                    "parameters": {}  # No environment parameters
                }
            })
        },
        # Databricks file
        {
            "path": "databricks/notebooks/process_customer_data.py",
            "change_type": "add",
            "content": """# Process Customer Data
import pyspark.sql.functions as F

# TODO: Fix this later
password = "admin123"  # Security issue!

# Read data
df = spark.read.parquet("/mnt/raw/customers")

# Process without caching
result = df.filter(F.col("active") == True).filter(F.col("country") == "US")

# Write result
result.write.mode("overwrite").parquet("/mnt/processed/us_customers")

print("Processing complete")
"""
        },
        # SQL file
        {
            "path": "sql/tables/create_customer_table.sql",
            "change_type": "add",
            "content": """-- Create customer table
CREATE TABLE customers (
    id INT,
    name VARCHAR(100),
    email VARCHAR(100),
    created_date DATETIME
);
-- No PRIMARY KEY!
-- No constraints!
"""
        }
    ],
    "repository": {
        "id": "test-repo-123",
        "name": "DataPlatform",
        "url": "https://dev.azure.com/org/project/_git/dataplatform"
    }
}


def test_validation():
    """Run the PR validation test"""
    print("🚀 Triggering PR validation...")
    print(f"   PR ID: {test_pr_data['pr_id']}")
    print(f"   Files: {len(test_pr_data['files'])}")
    print()

    try:
        # Send the request
        print("📤 Sending request to the API...")
        response = requests.post(
            API_URL,
            headers=headers,
            json=test_pr_data,
            timeout=300  # 5 minutes timeout
        )
        print(f"✅ Status: {response.status_code}")
        print(response.json())
        # Check the response
        if response.status_code == 200:
            result = response.json()

            print("✅ Validation completed successfully!")
            print("\n" + "=" * 60)
            print(" VALIDATION RESULTS")
            print("=" * 60)

            # Summary
            print(f"\n📊 Summary:")
            print(f"   - Production Ready: {'✅ YES' if result['production_ready'] else '❌ NO'}")
            print(f"   - Technologies detected: {', '.join(result['technologies_detected'])}")
            print(f"   - Critical issues: {result['critical_issues_count']}")
            print(f"   - Duration: {result.get('validation_duration', 0):.2f} seconds")

            # Checkpoint results
            print(f"\n📋 Checkpoint results:")
            for checkpoint in result.get('checkpoint_results', []):
                status_icon = "✅" if checkpoint['status'] == "PASS" else "❌"
                print(f"\n   {status_icon} {checkpoint['technology']} - {checkpoint['checkpoint_name']}")
                print(f"      Severity: {checkpoint['severity']}")

                if checkpoint['violations']:
                    print(f"      Violations:")
                    for violation in checkpoint['violations']:
                        print(f"        - {violation}")
                    print(f"      Suggestions:")
                    for suggestion in checkpoint['suggestions']:
                        print(f"        - {suggestion}")

            # Remediation plan
            if not result['production_ready'] and result.get('remediation_plan'):
                plan = result['remediation_plan']
                print(f"\n🔧 Remediation Plan:")
                print(f"   - Immediate actions: {len(plan.get('immediate_actions', []))}")
                print(f"   - High priority actions: {len(plan.get('high_priority_actions', []))}")
                print(f"   - Estimated effort: {plan.get('estimated_effort', {}).get('critical', 0)} hours")

            # Save the report
            report_file = f"validation_report_{test_pr_data['pr_id']}.json"
            with open(report_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n💾 Report saved in: {report_file}")

        else:
            print(f"❌ Error {response.status_code}: {response.text}")

    except requests.exceptions.Timeout:
        print("⏱️ Timeout - validation takes more than 5 minutes")
    except requests.exceptions.ConnectionError:
        print("❌ Unable to connect to the API")
        print("   Make sure the API is running: uvicorn api.main:app --reload")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    print("=" * 60)
    print(" 🧪 PR VALIDATION TEST WITH CREWAI")
    print("=" * 60)

    # Check configuration
    print("\n⚙️  Configuration:")
    print(f"   - API URL: {API_URL}")
    print(f"   - API Key: {'*' * 8}...{API_KEY[-4:] if len(API_KEY) > 4 else 'NOT SET'}")

    print("\n" + "-" * 60)
    input("Press ENTER to start validation...")

    test_validation()

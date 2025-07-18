# Azure Data Factory Validation Tools

from crewai_tools import tool
from typing import Dict, Any, List, Optional
import json
import re

from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("tools.adf_tools")


@tool("check_adf_naming_convention")
def check_adf_naming_convention_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check ADF resource naming conventions

    Args:
        files: List of ADF files to validate

    Returns:
        Validation results with violations and suggestions
    """
    logger.info(f"Checking naming conventions for {len(files)} ADF files")

    violations = []
    suggestions = []

    # Naming patterns for different ADF resources
    naming_patterns = {
        "pipeline": r"^[a-z][a-z0-9_]*_pipeline$",
        "dataset": r"^[a-z][a-z0-9_]*_dataset$",
        "linkedservice": r"^[a-z][a-z0-9_]*_ls$",
        "dataflow": r"^[a-z][a-z0-9_]*_dataflow$",
        "trigger": r"^[a-z][a-z0-9_]*_trigger$"
    }

    for file in files:
        try:
            content = json.loads(file.get("content", "{}"))
            resource_name = content.get("name", "")
            resource_type = content.get("type", "").split("/")[-1].lower()

            if resource_type in naming_patterns:
                pattern = naming_patterns[resource_type]
                if not re.match(pattern, resource_name):
                    violations.append(
                        f"{file['path']}: Resource '{resource_name}' does not follow naming convention for {resource_type}"
                    )
                    suggestions.append(
                        f"{file['path']}: Rename '{resource_name}' to follow pattern '{pattern}' (e.g., 'customer_data_{resource_type}')"
                    )

            # Check length constraint
            if len(resource_name) > 140:
                violations.append(
                    f"{file['path']}: Resource name '{resource_name}' exceeds 140 characters"
                )
                suggestions.append(
                    f"{file['path']}: Shorten the resource name to under 140 characters"
                )

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON for {file['path']}")
            violations.append(f"{file['path']}: Invalid JSON format")
            suggestions.append(f"{file['path']}: Fix JSON syntax errors")

    return {
        "checkpoint": "ADF Naming Convention",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "HIGH"
    }


@tool("check_adf_pipeline_pattern")
def check_adf_pipeline_pattern_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check for single parent pipeline pattern implementation
    """
    logger.info("Checking pipeline patterns")

    violations = []
    suggestions = []

    pipelines = []
    for file in files:
        try:
            content = json.loads(file.get("content", "{}"))
            if content.get("type") == "Microsoft.DataFactory/factories/pipelines":
                pipelines.append({
                    "name": content.get("name"),
                    "path": file["path"],
                    "activities": content.get("properties", {}).get("activities", [])
                })
        except:
            pass

    # Check for parent-child pattern
    parent_pipelines = []
    child_pipelines = []

    for pipeline in pipelines:
        has_execute_pipeline = any(
            activity.get("type") == "ExecutePipeline"
            for activity in pipeline["activities"]
        )

        if has_execute_pipeline:
            parent_pipelines.append(pipeline["name"])
        else:
            # Check if this pipeline might be processing individual tables
            for activity in pipeline["activities"]:
                if activity.get("type") in ["Copy", "DataFlow"] and "table" in pipeline["name"].lower():
                    child_pipelines.append(pipeline["name"])
                    break

    # If we have multiple pipelines processing individual tables without a parent
    if len(child_pipelines) > 3 and len(parent_pipelines) == 0:
        violations.append(
            "Multiple pipelines processing individual tables detected without a parent orchestrator"
        )
        suggestions.append(
            "Create a parent pipeline that orchestrates child pipelines using ExecutePipeline activities"
        )

    return {
        "checkpoint": "Single Parent Pipeline Pattern",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "MEDIUM"
    }


@tool("check_adf_security")
def check_adf_security_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check ADF security best practices
    """
    logger.info("Checking ADF security practices")

    violations = []
    suggestions = []

    # Security patterns to detect
    security_risks = [
        (r'"password"\s*:\s*"[^"]*"', "Hardcoded password detected"),
        (r'"accountKey"\s*:\s*"[^"]*"', "Hardcoded account key detected"),
        (r'"connectionString"\s*:\s*"[^"]*Data Source', "Hardcoded connection string detected"),
        (r'"sasToken"\s*:\s*"[^"]*"', "Hardcoded SAS token detected"),
        (r'"clientSecret"\s*:\s*"[^"]*"', "Hardcoded client secret detected")
    ]

    for file in files:
        content = file.get("content", "")

        # Check for hardcoded credentials
        for pattern, risk_message in security_risks:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"{file['path']}: {risk_message}")
                suggestions.append(
                    f"{file['path']}: Use Azure Key Vault or Managed Service Identity (MSI) for authentication"
                )

        # Check for Key Vault or MSI usage
        try:
            content_json = json.loads(content)
            if content_json.get("type") == "Microsoft.DataFactory/factories/linkedservices":
                properties = content_json.get("properties", {})
                type_properties = properties.get("typeProperties", {})

                # Check if using secure authentication
                auth_type = type_properties.get("authenticationType", "")
                if auth_type not in ["ManagedServiceIdentity", "ServicePrincipal"]:
                    if "keyvault" not in json.dumps(type_properties).lower():
                        violations.append(
                            f"{file['path']}: Linked service not using MSI or Key Vault authentication"
                        )
                        suggestions.append(
                            f"{file['path']}: Configure MSI or Key Vault reference for secure authentication"
                        )
        except:
            pass

    return {
        "checkpoint": "Security Best Practices",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "CRITICAL"
    }


@tool("check_adf_parameterization")
def check_adf_parameterization_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check if pipelines use proper parameterization for environment-specific values
    """
    logger.info("Checking ADF parameterization")

    violations = []
    suggestions = []

    # Environment-specific patterns that should be parameterized
    env_patterns = [
        (r'dev\.', "Development environment reference"),
        (r'test\.', "Test environment reference"),
        (r'prod\.', "Production environment reference"),
        (r'https?://[^/]*\.(blob|dfs)\.core\.windows\.net', "Storage account URL"),
        (r'\.database\.windows\.net', "SQL Server URL"),
        (r'/subscriptions/[a-f0-9\-]+/', "Subscription ID")
    ]

    for file in files:
        try:
            content = file.get("content", "")
            content_json = json.loads(content)

            # Check for hardcoded environment-specific values
            for pattern, description in env_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Check if it's properly parameterized
                    if "@pipeline().globalParameters" not in content and "@dataset().parameters" not in content:
                        violations.append(
                            f"{file['path']}: {description} should be parameterized"
                        )
                        suggestions.append(
                            f"{file['path']}: Use global parameters or pipeline parameters for {description}"
                        )

            # Check if pipeline has parameters defined
            if content_json.get("type") == "Microsoft.DataFactory/factories/pipelines":
                parameters = content_json.get("properties", {}).get("parameters", {})
                if not parameters and any(re.search(p[0], content) for p in env_patterns):
                    violations.append(
                        f"{file['path']}: Pipeline contains environment-specific values but no parameters defined"
                    )
                    suggestions.append(
                        f"{file['path']}: Add parameters section to pipeline for environment-specific values"
                    )

        except:
            pass

    return {
        "checkpoint": "Parameterization Check",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "HIGH"
    }


@tool("check_adf_validation")
def check_adf_validation_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check if ADF resources pass basic validation
    """
    logger.info("Performing ADF validation checks")

    violations = []
    suggestions = []

    for file in files:
        try:
            content = json.loads(file.get("content", "{}"))

            # Basic structure validation
            if "name" not in content:
                violations.append(f"{file['path']}: Missing 'name' property")
                suggestions.append(f"{file['path']}: Add a 'name' property to the resource")

            if "type" not in content:
                violations.append(f"{file['path']}: Missing 'type' property")
                suggestions.append(f"{file['path']}: Add a 'type' property to the resource")

            if "properties" not in content:
                violations.append(f"{file['path']}: Missing 'properties' section")
                suggestions.append(f"{file['path']}: Add a 'properties' section to the resource")

            # Pipeline-specific validation
            if content.get("type") == "Microsoft.DataFactory/factories/pipelines":
                activities = content.get("properties", {}).get("activities", [])
                if not activities:
                    violations.append(f"{file['path']}: Pipeline has no activities")
                    suggestions.append(f"{file['path']}: Add at least one activity to the pipeline")

                # Check activity dependencies
                for activity in activities:
                    if "name" not in activity:
                        violations.append(f"{file['path']}: Activity missing 'name' property")
                        suggestions.append(f"{file['path']}: Add name to all activities")

                    if "type" not in activity:
                        violations.append(f"{file['path']}: Activity missing 'type' property")
                        suggestions.append(f"{file['path']}: Specify activity type")

        except json.JSONDecodeError:
            violations.append(f"{file['path']}: Invalid JSON structure")
            suggestions.append(f"{file['path']}: Validate JSON syntax using ADF validation")

    return {
        "checkpoint": "ADF Validation",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "CRITICAL"
    }


@tool("check_adf_error_handling")
def check_adf_error_handling_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check error handling and failure alerts configuration
    """
    logger.info("Checking ADF error handling")

    violations = []
    suggestions = []

    for file in files:
        try:
            content = json.loads(file.get("content", "{}"))

            if content.get("type") == "Microsoft.DataFactory/factories/pipelines":
                properties = content.get("properties", {})
                activities = properties.get("activities", [])

                # Check for error handling in activities
                for activity in activities:
                    activity_name = activity.get("name", "Unknown")

                    # Check for retry policy
                    policy = activity.get("policy", {})
                    if "retry" not in policy:
                        violations.append(
                            f"{file['path']}: Activity '{activity_name}' has no retry policy"
                        )
                        suggestions.append(
                            f"{file['path']}: Add retry policy to activity '{activity_name}'"
                        )

                    # Check for failure dependencies
                    depends_on = activity.get("dependsOn", [])
                    has_failure_handling = any(
                        dep.get("dependencyConditions", []) and
                        "Failed" in dep.get("dependencyConditions", [])
                        for dep in depends_on
                    )

                    # Check if critical activities have failure handling
                    if activity.get("type") in ["Copy", "DataFlow", "ExecutePipeline"] and not has_failure_handling:
                        # Look for error handling activities
                        error_handlers = [
                            a for a in activities
                            if any(
                                dep.get("activity") == activity_name and
                                "Failed" in dep.get("dependencyConditions", [])
                                for dep in a.get("dependsOn", [])
                            )
                        ]

                        if not error_handlers:
                            violations.append(
                                f"{file['path']}: No error handling for critical activity '{activity_name}'"
                            )
                            suggestions.append(
                                f"{file['path']}: Add error handling activity with email notification for '{activity_name}'"
                            )

                # Check for email alerts
                has_email_activity = any(
                    activity.get("type") == "Web" and
                    "mail" in json.dumps(activity).lower()
                    for activity in activities
                )

                if not has_email_activity:
                    violations.append(
                        f"{file['path']}: No email notification activity found for failures"
                    )
                    suggestions.append(
                        f"{file['path']}: Add Web activity to send email notifications on pipeline failures"
                    )

        except:
            pass

    return {
        "checkpoint": "Error Handling and Alerts",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "CRITICAL"
    }
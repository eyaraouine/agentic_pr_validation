# src/tools/adf_tools.py - Fixed version

from crewai_tools import tool
from typing import Dict, Any, List, Optional, Union
import json
import re

from src.config import get_llm_instance
from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("tools.adf_tools")


def ensure_file_list(files: Union[List[Any], str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensure files parameter is a proper list of dictionaries with content
    """
    # If it's a single dict (from CrewAI), wrap it in a list
    if isinstance(files, dict) and "files" in files:
        files = files["files"]

    # Handle string input
    if isinstance(files, str):
        # Try to parse as JSON
        try:
            parsed = json.loads(files)
            if isinstance(parsed, dict) and "files" in parsed:
                files = parsed["files"]
            elif isinstance(parsed, list):
                files = parsed
            else:
                files = [parsed]
        except:
            # If not JSON, assume it's a single file path
            files = [{"path": files, "content": ""}]

    # Ensure it's a list
    if not isinstance(files, list):
        files = [files]

    # Convert each file to proper dict format with content
    result = []
    for file in files:
        if isinstance(file, str):
            # Try to parse string as JSON first
            try:
                file_dict = json.loads(file)
                if isinstance(file_dict, dict):
                    result.append({
                        "path": file_dict.get("path", ""),
                        "content": file_dict.get("content", "")
                    })
                else:
                    result.append({"path": file, "content": ""})
            except:
                result.append({"path": file, "content": ""})
        elif isinstance(file, dict):
            # Ensure we have both path and content
            result.append({
                "path": file.get("path", ""),
                "content": file.get("content", "")
            })
        else:
            # Try to extract attributes from object
            result.append({
                "path": getattr(file, "path", ""),
                "content": getattr(file, "content", "")
            })

    return result

@tool("check_all_adf_compliance")
def check_all_adf_compliance_tool(files: Union[List[Dict[str, Any]], str, Dict[str, Any]]) -> str:
    """
    Run ALL ADF compliance checks and return complete results.
    Ensures that all validation tools for ADF (Azure Data Factory) are executed.

    Args:
        files: List of ADF files to validate (dict, list, or JSON string)

    Returns:
        JSON string with all validation results
    """
    logger.info("Running ALL ADF compliance checks")

    files_list = ensure_file_list(files)
    results = {}

    try:
        results["naming_convention"] = check_adf_naming_convention_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in naming check: {e}")
        results["naming_convention"] = {
            "checkpoint": "ADF Naming Convention",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "HIGH"
        }

    try:
        results["security_best_practices"] = check_adf_security_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in security check: {e}")
        results["security_best_practices"] = {
            "checkpoint": "Security Best Practices",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "CRITICAL"
        }

    try:
        results["pipeline_pattern"] = check_adf_pipeline_pattern_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in pipeline pattern check: {e}")
        results["pipeline_pattern"] = {
            "checkpoint": "Single Parent Pipeline Pattern",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "MEDIUM"
        }

    try:
        results["parameterization"] = check_adf_parameterization_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in parameterization check: {e}")
        results["parameterization"] = {
            "checkpoint": "Parameterization Check",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "HIGH"
        }

    try:
        results["validation"] = check_adf_validation_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in validation check: {e}")
        results["validation"] = {
            "checkpoint": "ADF Validation",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "CRITICAL"
        }

    try:
        results["error_handling"] = check_adf_error_handling_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in error handling check: {e}")
        results["error_handling"] = {
            "checkpoint": "Error Handling and Alerts",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "CRITICAL"
        }
    llm = get_llm_instance()

    for check_name, check_data in results.items():
        if isinstance(check_data, dict) and check_data.get('status') == 'FAIL':
            violations = check_data.get('violations', [])

            if violations:
                ai_suggestions = []

                for violation in violations:
                    file_path = violation.split(':')[0] if ':' in violation else ""
                    file_content = next((f.get('content', '') for f in files_list if f.get('path') == file_path), '')

                    prompt = f"""
                    Fix this ADF violation: {violation}
                   
                   Code:```json\n{file_content}\n```
                        
                        Provide ONLY the exact code fix needed. Be concise - maximum 2 sentences explanation.
                        """

                    response = llm.invoke(prompt)
                    ai_suggestion = response.content if hasattr(response, 'content') else str(response)
                    ai_suggestions.append(ai_suggestion)

                check_data['generic_suggestions'] = check_data.get('suggestions', [])
                check_data['ai_suggestions'] = ai_suggestions


    return json.dumps(results, indent=2)

@tool("check_adf_naming_convention")
def check_adf_naming_convention_tool(files: Union[List[Dict[str, Any]], List[str]]) -> Dict[str, Any]:
    """
    Check ADF resource naming conventions

    Args:
        files: List of ADF files to validate (can be dicts or strings)

    Returns:
        Validation results with violations and suggestions
    """
    logger.info(f"Checking naming conventions for {len(files)} ADF files")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files")

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

    for file in files_list:
        file_path = file.get("path", "")
        content = file.get("content", "")

        if not content:
            logger.warning(f"No content provided for {file_path}")
            continue

        try:
            content_json = json.loads(content)
            resource_name = content_json.get("name", "")
            resource_type = content_json.get("type", "").split("/")[-1].lower()

            if resource_type in naming_patterns:
                pattern = naming_patterns[resource_type]
                if not re.match(pattern, resource_name):
                    violations.append(
                        f"{file_path}: Resource '{resource_name}' does not follow naming convention for {resource_type}"
                    )
                    suggestions.append(
                        f"{file_path}: Rename '{resource_name}' to follow pattern '{pattern}' (e.g., 'customer_data_{resource_type}')"
                    )

            # Check length constraint
            if len(resource_name) > 140:
                violations.append(
                    f"{file_path}: Resource name '{resource_name}' exceeds 140 characters"
                )
                suggestions.append(
                    f"{file_path}: Shorten the resource name to under 140 characters"
                )

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON for {file_path}")
            violations.append(f"{file_path}: Invalid JSON format")
            suggestions.append(f"{file_path}: Fix JSON syntax errors")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")

    return {
        "checkpoint": "ADF Naming Convention",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "HIGH"
    }


@tool("check_adf_security")
def check_adf_security_tool(files: Union[List[Dict[str, Any]], List[str]]) -> Dict[str, Any]:
    """
    Check ADF security best practices
    """
    logger.info("Checking ADF security practices")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files for security")

    violations = []
    suggestions = []

    # Security patterns to detect
    security_risks = [
        (r'"password"\s*:\s*"[^"]*"', "Hardcoded password detected"),
        (r'"accountKey"\s*:\s*"[^"]*"', "Hardcoded account key detected"),
        (r'"connectionString"\s*:\s*"[^"]*Data Source', "Hardcoded connection string detected"),
        (r'"sasToken"\s*:\s*"[^"]*"', "Hardcoded SAS token detected"),
        (r'"clientSecret"\s*:\s*"[^"]*"', "Hardcoded client secret detected"),
        (r'Password\s*=\s*[^;]+', "Password in connection string detected")
    ]

    for file in files_list:
        file_path = file.get("path", "")
        content = file.get("content", "")

        if not content:
            logger.warning(f"No content provided for {file_path}")
            continue

        # Check for hardcoded credentials
        for pattern, risk_message in security_risks:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"{file_path}: {risk_message}")
                suggestions.append(
                    f"{file_path}: Use Azure Key Vault or Managed Service Identity (MSI) for authentication"
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
                            f"{file_path}: Linked service not using MSI or Key Vault authentication"
                        )
                        suggestions.append(
                            f"{file_path}: Configure MSI or Key Vault reference for secure authentication"
                        )
        except Exception as e:
            logger.debug(f"Could not parse as linked service: {file_path}")

    return {
        "checkpoint": "Security Best Practices",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "CRITICAL"
    }


# Update other tools similarly...
@tool("check_adf_pipeline_pattern")
def check_adf_pipeline_pattern_tool(files: Union[List[Dict[str, Any]], List[str]]) -> Dict[str, Any]:
    """
    Check for single parent pipeline pattern implementation
    """
    logger.info("Checking pipeline patterns")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files for patterns")

    violations = []
    suggestions = []
    pipelines = []
    for file in files_list:
        content = file.get("content", "")
        if not content:
            continue

        try:
            content_json = json.loads(content)
            if content_json.get("type") == "Microsoft.DataFactory/factories/pipelines":
                pipelines.append({
                    "name": content_json.get("name"),
                    "path": file.get("path", ""),
                    "activities": content_json.get("properties", {}).get("activities", [])
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


@tool("check_adf_parameterization")
def check_adf_parameterization_tool(files: Union[List[Dict[str, Any]], List[str]]) -> Dict[str, Any]:
    """
    Check if pipelines use proper parameterization for environment-specific values
    """
    logger.info("Checking ADF parameterization")

    # Ensure proper file list format
    files_list = ensure_file_list(files)

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

    for file in files_list:
        content = file.get("content", "")
        file_path = file.get("path", "")

        if not content:
            continue

        try:
            content_json = json.loads(content)

            # Check for hardcoded environment-specific values
            for pattern, description in env_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Check if it's properly parameterized
                    if "@pipeline().globalParameters" not in content and "@dataset().parameters" not in content:
                        violations.append(
                            f"{file_path}: {description} should be parameterized"
                        )
                        suggestions.append(
                            f"{file_path}: Use global parameters or pipeline parameters for {description}"
                        )

            # Check if pipeline has parameters defined
            if content_json.get("type") == "Microsoft.DataFactory/factories/pipelines":
                parameters = content_json.get("properties", {}).get("parameters", {})
                if not parameters and any(re.search(p[0], content) for p in env_patterns):
                    violations.append(
                        f"{file_path}: Pipeline contains environment-specific values but no parameters defined"
                    )
                    suggestions.append(
                        f"{file_path}: Add parameters section to pipeline for environment-specific values"
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
def check_adf_validation_tool(files: Union[List[Dict[str, Any]], List[str]]) -> Dict[str, Any]:
    """
    Check if ADF resources pass basic validation
    """
    logger.info("Performing ADF validation checks")

    logger.info("Checking ADF security practices")

    # Ensure proper file list format
    files_list = ensure_file_list(files)

    violations = []
    suggestions = []

    for file in files_list:
        content = file.get("content", "")
        file_path = file.get("path", "")

        if not content:
            violations.append(f"{file_path}: No content provided for validation")
            continue

        try:
            content_json = json.loads(content)

            # Basic structure validation
            if "name" not in content_json:
                violations.append(f"{file_path}: Missing 'name' property")
                suggestions.append(f"{file_path}: Add a 'name' property to the resource")

            if "type" not in content_json:
                violations.append(f"{file_path}: Missing 'type' property")
                suggestions.append(f"{file_path}: Add a 'type' property to the resource")

            if "properties" not in content_json:
                violations.append(f"{file_path}: Missing 'properties' section")
                suggestions.append(f"{file_path}: Add a 'properties' section to the resource")

            # Pipeline-specific validation
            if content_json.get("type") == "Microsoft.DataFactory/factories/pipelines":
                activities = content_json.get("properties", {}).get("activities", [])
                if not activities:
                    violations.append(f"{file_path}: Pipeline has no activities")
                    suggestions.append(f"{file_path}: Add at least one activity to the pipeline")

                # Check activity structure
                for idx, activity in enumerate(activities):
                    if "name" not in activity:
                        violations.append(f"{file_path}: Activity {idx} missing 'name' property")
                        suggestions.append(f"{file_path}: Add name to all activities")

                    if "type" not in activity:
                        violations.append(f"{file_path}: Activity {idx} missing 'type' property")
                        suggestions.append(f"{file_path}: Specify activity type")

        except json.JSONDecodeError:
            violations.append(f"{file_path}: Invalid JSON structure")
            suggestions.append(f"{file_path}: Validate JSON syntax using ADF validation")

    return {
        "checkpoint": "ADF Validation",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "CRITICAL"
    }


@tool("check_adf_error_handling")
def check_adf_error_handling_tool(files: Union[List[Dict[str, Any]], List[str]]) -> Dict[str, Any]:
    """
    Check error handling and failure alerts configuration
    """
    logger.info("Checking ADF error handling")


    # Ensure proper file list format
    files_list = ensure_file_list(files)

    violations = []
    suggestions = []

    for file in files_list:
        content = file.get("content", "")
        file_path = file.get("path", "")

        if not content:
            continue

        try:
            content_json = json.loads(content)

            if content_json.get("type") == "Microsoft.DataFactory/factories/pipelines":
                properties = content_json.get("properties", {})
                activities = properties.get("activities", [])

                # Check for error handling in activities
                for activity in activities:
                    activity_name = activity.get("name", "Unknown")

                    # Check for retry policy
                    policy = activity.get("policy", {})
                    if "retry" not in policy:
                        violations.append(
                            f"{file_path}: Activity '{activity_name}' has no retry policy"
                        )
                        suggestions.append(
                            f"{file_path}: Add retry policy to activity '{activity_name}'"
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
                                f"{file_path}: No error handling for critical activity '{activity_name}'"
                            )
                            suggestions.append(
                                f"{file_path}: Add error handling activity with email notification for '{activity_name}'"
                            )

                # Check for email alerts
                has_email_activity = any(
                    activity.get("type") == "Web" and
                    "mail" in json.dumps(activity).lower()
                    for activity in activities
                )

                if not has_email_activity:
                    violations.append(
                        f"{file_path}: No email notification activity found for failures"
                    )
                    suggestions.append(
                        f"{file_path}: Add Web activity to send email notifications on pipeline failures"
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
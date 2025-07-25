# Azure SQL Validation Tools

from crewai_tools import tool
from typing import Dict, Any, List, Optional, Union
import re
import sqlparse
import json

from src.config import get_llm_instance
from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("tools.sql_tools")


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


@tool("check_all_sql_compliance")
def check_all_sql_compliance_tool(files: List[Dict[str, Any]]) -> str:
    """
    Run ALL SQL compliance checks and return complete results.
    Automatically detects if stored procedures check is needed based on file content.
    This ensures all checks are executed even if agent times out.

    Args:
        files: List of SQL files to validate

    Returns:
        JSON string with all validation results
    """
    logger.info("Running ALL SQL compliance checks")

    # Ensure proper file list format
    files_list = ensure_file_list(files)

    # Auto-detect if stored procedures check is needed
    should_check_procedures = False
    for file in files_list:
        content = file.get("content", "").upper()
        if content:
            # Check if file contains procedures or complex logic that might need procedures
            if any([
                "CREATE PROCEDURE" in content,
                "ALTER PROCEDURE" in content,
                content.count("JOIN") > 2,
                "CURSOR" in content,
                "WHILE" in content,
                content.count("CASE WHEN") > 3,
                "MERGE" in content
            ]):
                should_check_procedures = True
                break

    logger.info(f"Stored procedures check needed: {should_check_procedures}")

    results = {}

    # Run all mandatory checks
    try:
        results["check_sql_constraints"] = check_sql_constraints_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in constraints check: {e}")
        results["check_sql_constraints"] = {
            "checkpoint": "Use Constraints (PK/FK)",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "HIGH"
        }

    try:
        results["check_sql_schemas"] = check_sql_schemas_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in schemas check: {e}")
        results["check_sql_schemas"] = {
            "checkpoint": "Use Schemas",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "MEDIUM"
        }

    try:
        results["check_sql_naming_convention"] = check_sql_naming_convention_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in naming convention check: {e}")
        results["check_sql_naming_convention"] = {
            "checkpoint": "Aligned Naming Convention",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "MEDIUM"
        }

    try:
        results["check_sql_security"] = check_sql_security_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in security check: {e}")
        results["check_sql_security"] = {
            "checkpoint": "Access Control",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "CRITICAL"
        }

    try:
        results["check_sql_version_control"] = check_sql_version_control_tool.func(files_list)
    except Exception as e:
        logger.error(f"Error in version control check: {e}")
        results["check_sql_version_control"] = {
            "checkpoint": "Version Control",
            "status": "FAIL",
            "violations": [f"Error running check: {str(e)}"],
            "suggestions": ["Fix the error and re-run the check"],
            "severity": "HIGH"
        }

    # Include stored procedures check only if needed
    if should_check_procedures:
        try:
            results["check_sql_stored_procedures"] = check_sql_stored_procedures_tool.func(files_list)
        except Exception as e:
            logger.error(f"Error in stored procedures check: {e}")
            results["check_sql_stored_procedures"] = {
                "checkpoint": "Use Stored Procedures",
                "status": "FAIL",
                "violations": [f"Error running check: {str(e)}"],
                "suggestions": ["Fix the error and re-run the check"],
                "severity": "MEDIUM"
            }
    else:
        logger.info("No stored procedures or complex logic found, skipping stored procedures check")

    llm = get_llm_instance()

    for check_name, check_data in results.items():
        if isinstance(check_data, dict) and check_data.get('status') == 'FAIL':
            violations = check_data.get('violations', [])

            if violations:
                detailed_solutions = []
                action_items = []

                for violation in violations:
                    file_path = violation.split(':')[0] if ':' in violation else ""
                    file_content = next((f.get('content', '') for f in files_list if f.get('path') == file_path), '')

                    # Detailed technical solution
                    detailed_prompt = f"""
                        Fix this SQL violation: {violation}
                   
                   Code: ```sql\n{file_content}\n```
                        
                     Provide  maximum 2 short sentences explanation and below provide ONLY the exact code fix needed. 
                        """

                    # Action item for managers
                    action_prompt = f"""
                        SQL compliance issue: {violation}
                        

                        Provide executive summary:
                        1. Business impact (1 short sentence)
                        2. Required action (specific steps)
                        3. Risk level if not fixed

                        BE CONCISE - Maximum 2 short sentences per section
                        
                        """

                    detailed_response = llm.invoke(detailed_prompt)
                    action_response = llm.invoke(action_prompt)

                    detailed_solutions.append(
                        detailed_response.content if hasattr(detailed_response, 'content') else str(detailed_response)
                    )
                    action_items.append(
                        action_response.content if hasattr(action_response, 'content') else str(action_response)
                    )

                check_data['generic_suggestions'] = check_data.get('suggestions', [])
                check_data['detailed_solutions'] = detailed_solutions
                check_data['action_items'] = action_items

    return json.dumps(results, indent=2)



@tool("check_sql_stored_procedures")
def check_sql_stored_procedures_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check if logic is properly encapsulated in stored procedures

    Args:
        files: List of SQL files to validate

    Returns:
        Validation results with violations and suggestions
    """
    logger.info(f"Checking stored procedures for {len(files)} SQL files")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files")

    violations = []
    suggestions = []

    for file in files_list:
        content = file.get("content", "").upper()
        file_path = file.get("path", "")

        if not content:
            logger.warning(f"No content provided for {file_path}")
            continue

        # Check if file contains business logic outside stored procedures
        has_complex_logic = any([
            content.count("JOIN") > 2,
            "CURSOR" in content,
            "WHILE" in content and "CREATE PROCEDURE" not in content,
            content.count("CASE WHEN") > 3,
            "MERGE" in content and "CREATE PROCEDURE" not in content
        ])

        if has_complex_logic and "CREATE PROCEDURE" not in content:
            violations.append(
                f"{file_path}: Complex business logic not encapsulated in stored procedure"
            )
            suggestions.append(
                f"{file_path}: Move complex logic into a stored procedure for reusability"
            )

        # Check stored procedure structure
        if "CREATE PROCEDURE" in content:
            # Check for proper error handling
            if "TRY" not in content or "CATCH" not in content:
                violations.append(f"{file_path}: Stored procedure missing TRY-CATCH error handling")
                suggestions.append(f"{file_path}: Add TRY-CATCH blocks for proper error handling")

            # Check for transaction management
            if "BEGIN TRANSACTION" in content and "COMMIT" not in content:
                violations.append(f"{file_path}: Transaction started but not committed")
                suggestions.append(f"{file_path}: Ensure all transactions are properly committed or rolled back")

    return {
        "checkpoint": "Use Stored Procedures",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "MEDIUM"
    }



@tool("check_sql_constraints")
def check_sql_constraints_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check for proper use of constraints (PK/FK)
    """
    logger.info("Checking SQL constraints")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files")

    violations = []
    suggestions = []

    for file in files_list:
        content = file.get("content", "").upper()
        file_path = file.get("path", "")

        if not content:
            logger.warning(f"No content provided for {file_path}")
            continue


        # Check CREATE TABLE statements
        if "CREATE TABLE" in content:
            # Extract table definitions
            tables = re.findall(r'CREATE\s+TABLE\s+(\w+)[^;]+;', content, re.IGNORECASE)

            for table in tables:
                table_pattern = rf'CREATE\s+TABLE\s+{table}[^;]+;'
                table_def = re.search(table_pattern, content, re.IGNORECASE)

                if table_def:
                    table_content = table_def.group()

                    # Check for primary key
                    if "PRIMARY KEY" not in table_content:
                        violations.append(f"{file_path}: Table '{table}' missing PRIMARY KEY constraint")
                        suggestions.append(f"{file_path}: Add PRIMARY KEY constraint to table '{table}'")

                    # Check for appropriate foreign keys
                    if "_ID" in table_content and "FOREIGN KEY" not in table_content:
                        violations.append(f"{file_path}: Table '{table}' has ID columns but no FOREIGN KEY constraints")
                        suggestions.append(f"{file_path}: Add FOREIGN KEY constraints for referential integrity")

                    # Check for NOT NULL constraints on important fields
                    if "NOT NULL" not in table_content:
                        violations.append(f"{file_path}: Table '{table}' has no NOT NULL constraints")
                        suggestions.append(f"{file_path}: Add NOT NULL constraints to required fields")

        # Check ALTER TABLE for constraints
        if "ALTER TABLE" in content and "ADD CONSTRAINT" not in content:
            if any(keyword in content for keyword in ["ADD COLUMN", "MODIFY COLUMN"]):
                violations.append(f"{file_path}: Schema changes without constraint considerations")
                suggestions.append(f"{file_path}: Review and add necessary constraints after schema changes")

    return {
        "checkpoint": "Use Constraints (PK/FK)",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "HIGH"
    }


@tool("check_sql_schemas")
def check_sql_schemas_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check for proper schema organization
    """
    logger.info("Checking SQL schema organization")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files")

    violations = []
    suggestions = []

    for file in files_list:

        file_path = file.get("path", "")
        content = file.get("content", "")

        if not content:
            logger.warning(f"No content provided for {file_path}")
            continue


        # Check if objects are created with schema prefix
        objects_without_schema = []

        # Patterns for database objects
        object_patterns = [
            r'CREATE\s+TABLE\s+(?!.*\.)(\w+)',
            r'CREATE\s+VIEW\s+(?!.*\.)(\w+)',
            r'CREATE\s+PROCEDURE\s+(?!.*\.)(\w+)',
            r'CREATE\s+FUNCTION\s+(?!.*\.)(\w+)'
        ]

        for pattern in object_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            objects_without_schema.extend(matches)

        if objects_without_schema:
            violations.append(
                f"{file_path}: Objects created without schema: {', '.join(set(objects_without_schema))}"
            )
            suggestions.append(
                f"{file_path}: Use schema prefix (e.g., 'dbo.TableName' or 'app.ProcedureName')"
            )

        # Check for CREATE SCHEMA statements
        if len(files) > 5 and not any("CREATE SCHEMA" in f.get("content", "") for f in files):
            violations.append("No schema definitions found in SQL files")
            suggestions.append("Create schemas to organize database objects logically")

        # Check for mixed schemas in same file
        schemas_used = re.findall(r'(\w+)\.\w+', content)
        unique_schemas = set(schemas_used)
        if len(unique_schemas) > 3:
            violations.append(f"{file_path}: Too many different schemas ({len(unique_schemas)}) in one file")
            suggestions.append(f"{file_path}: Organize objects by schema in separate files")

    return {
        "checkpoint": "Use Schemas",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "MEDIUM"
    }


@tool("check_sql_naming_convention")
def check_sql_naming_convention_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check SQL naming conventions
    """
    logger.info("Checking SQL naming conventions")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files")

    violations = []
    suggestions = []

    # Define naming patterns
    naming_rules = {
        "table": r'^[A-Z][a-zA-Z0-9]*$',  # PascalCase
        "column": r'^[A-Z][a-zA-Z0-9]*$',  # PascalCase
        "procedure": r'^(sp_|usp_)[a-z][a-zA-Z0-9_]*$',  # sp_ or usp_ prefix
        "function": r'^(fn_|ufn_)[a-z][a-zA-Z0-9_]*$',  # fn_ or ufn_ prefix
        "view": r'^(v_|vw_)[a-zA-Z0-9_]*$',  # v_ or vw_ prefix
        "index": r'^(IX_|IDX_)[a-zA-Z0-9_]*$'  # IX_ or IDX_ prefix
    }

    for file in files_list:
        content = file.get("content", "")
        file_path = file.get("path", "")
        if not content:
            logger.warning(f"No content provided for {file_path}")
            continue

        # Check table names
        tables = re.findall(r'CREATE\s+TABLE\s+(?:\[?(?:\w+)\]?\.)?\[?(\w+)\]?', content, re.IGNORECASE)
        for table in tables:
            # Skip schema names
            if table.upper() in ['DBO', 'SYS', 'INFORMATION_SCHEMA']:
                continue
            if not re.match(naming_rules["table"], table):
                violations.append(f"{file_path}: Table '{table}' doesn't follow PascalCase convention")
                suggestions.append(f"{file_path}: Rename table to PascalCase (e.g., 'CustomerOrders')")
        # Check stored procedures
        procedures = re.findall(r'CREATE\s+PROCEDURE\s+\[?(\w+)\]?', content, re.IGNORECASE)
        for proc in procedures:
            if not re.match(naming_rules["procedure"], proc):
                violations.append(f"{file_path}: Procedure '{proc}' doesn't follow naming convention")
                suggestions.append(f"{file_path}: Use 'sp_' or 'usp_' prefix (e.g., 'sp_GetCustomerOrders')")

        # Check functions
        functions = re.findall(r'CREATE\s+FUNCTION\s+\[?(\w+)\]?', content, re.IGNORECASE)
        for func in functions:
            if not re.match(naming_rules["function"], func):
                violations.append(f"{file_path}: Function '{func}' doesn't follow naming convention")
                suggestions.append(f"{file_path}: Use 'fn_' or 'ufn_' prefix (e.g., 'fn_CalculateTotal')")

        # Check views
        views = re.findall(r'CREATE\s+VIEW\s+\[?(\w+)\]?', content, re.IGNORECASE)
        for view in views:
            if not re.match(naming_rules["view"], view):
                violations.append(f"{file_path}: View '{view}' doesn't follow naming convention")
                suggestions.append(f"{file_path}: Use 'v_' or 'vw_' prefix (e.g., 'vw_CustomerSummary')")

    return {
        "checkpoint": "Aligned Naming Convention",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "MEDIUM"
    }


@tool("check_sql_security")
def check_sql_security_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check SQL security and access control
    """
    logger.info("Checking SQL security practices")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files")

    violations = []
    suggestions = []

    for file in files_list:
        content = file.get("content", "").upper()
        file_path = file.get("path", "")
        if not content:
            logger.warning(f"No content provided for {file_path}")
            continue

        # Check for GRANT statements
        has_grants = "GRANT" in content
        has_schema_level_grants = re.search(r'GRANT\s+\w+\s+ON\s+SCHEMA::', content)

        # Check for dangerous permissions
        dangerous_grants = [
            (r'GRANT\s+ALL', "GRANT ALL permissions detected"),
            (r'GRANT\s+CONTROL', "GRANT CONTROL permissions detected"),
            (r'GRANT\s+ALTER', "GRANT ALTER permissions detected"),
            (r'TO\s+PUBLIC', "Permissions granted to PUBLIC")
        ]

        for pattern, message in dangerous_grants:
            if re.search(pattern, content):
                violations.append(f"{file_path}: {message}")
                suggestions.append(f"{file_path}: Use principle of least privilege, grant only necessary permissions")

        # Check for dynamic SQL without proper validation
        if "EXEC(" in content or "EXECUTE(" in content:
            if not re.search(r'QUOTENAME|sp_executesql', content):
                violations.append(f"{file_path}: Dynamic SQL without proper parameterization")
                suggestions.append(f"{file_path}: Use sp_executesql with parameters or QUOTENAME for dynamic SQL")

        # Check for SQL injection vulnerabilities
        if re.search(r'@\w+.*\+.*@\w+', content):  # String concatenation with parameters
            violations.append(f"{file_path}: Potential SQL injection via string concatenation")
            suggestions.append(f"{file_path}: Use parameterized queries instead of string concatenation")

        # Check if creating objects without access control
        if any(keyword in content for keyword in ["CREATE TABLE", "CREATE VIEW", "CREATE PROCEDURE"]):
            if not has_grants and not has_schema_level_grants:
                violations.append(f"{file_path}: Objects created without explicit access control")
                suggestions.append(f"{file_path}: Add GRANT statements to control access at schema level")

        # Check for hardcoded credentials
        if re.search(r'PASSWORD\s*=\s*[\'"][^\'"]+[\'"]', content):
            violations.append(f"{file_path}: Hardcoded password detected")
            suggestions.append(f"{file_path}: Use Windows Authentication or Azure AD authentication")

    return {
        "checkpoint": "Access Control",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "CRITICAL"
    }


@tool("check_sql_version_control")
def check_sql_version_control_tool(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check if SQL scripts are properly versioned
    """
    logger.info("Checking SQL version control practices")

    # Ensure proper file list format
    files_list = ensure_file_list(files)
    logger.info(f"Processing {len(files_list)} files")

    violations = []
    suggestions = []

    for file in files_list:

        file_path = file.get("path", "")
        content = file.get("content", "")

        if not content:
            logger.warning(f"No content provided for {file_path}")
            continue

        # Check for version headers
        has_version_header = any([
            re.search(r'--\s*Version:', content, re.IGNORECASE),
            re.search(r'/\*\s*Version:', content, re.IGNORECASE),
            re.search(r'--\s*@version', content, re.IGNORECASE)
        ])

        # Check for change history
        has_change_history = any([
            re.search(r'--\s*Change\s*History:', content, re.IGNORECASE),
            re.search(r'--\s*Modified:', content, re.IGNORECASE),
            re.search(r'--\s*Date.*Author.*Description', content, re.IGNORECASE)
        ])

        # Check for author information
        has_author = any([
            re.search(r'--\s*Author:', content, re.IGNORECASE),
            re.search(r'--\s*Created\s*by:', content, re.IGNORECASE),
            re.search(r'--\s*@author', content, re.IGNORECASE)
        ])

        if not has_version_header:
            violations.append(f"{file_path}: Missing version information")
            suggestions.append(f"{file_path}: Add version header (e.g., '-- Version: 1.0.0')")

        if not has_change_history:
            violations.append(f"{file_path}: Missing change history")
            suggestions.append(f"{file_path}: Add change history section to track modifications")

        if not has_author:
            violations.append(f"{file_path}: Missing author information")
            suggestions.append(f"{file_path}: Add author information in header comments")

        # Check for migration scripts pattern
        if "migration" in file_path.lower() or "upgrade" in file_path.lower():
            if not re.search(r'\d{4}[-_]\d{2}[-_]\d{2}', file_path):
                violations.append(f"{file_path}: Migration script without date in filename")
                suggestions.append(
                    f"{file_path}: Use date prefix for migration scripts (e.g., '2024-01-15_add_customer_table.sql')")

    return {
        "checkpoint": "Version Control",
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "suggestions": suggestions,
        "severity": "HIGH"
    }
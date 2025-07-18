# Base Validator Class

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import re
from datetime import datetime

from src.models.checkpoint import CheckpointResult, CheckpointStatus, Severity
from src.models.technology import Technology
from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()


class BaseValidator(ABC):
    """Abstract base class for technology validators"""

    def __init__(self, technology: Technology):
        """
        Initialize validator

        Args:
            technology: Technology definition
        """
        self.technology = technology
        self.logger = setup_logger(f"validators.{technology.name}")

    @abstractmethod
    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """
        Get list of checkpoints for this technology

        Returns:
            List of checkpoint definitions
        """
        pass

    def validate_files(self, files: List[Dict[str, Any]]) -> List[CheckpointResult]:
        """
        Validate files against all checkpoints

        Args:
            files: List of files to validate

        Returns:
            List of checkpoint results
        """
        results = []
        checkpoints = self.get_checkpoints()

        self.logger.info(f"Starting validation for {len(files)} files with {len(checkpoints)} checkpoints")

        for checkpoint in checkpoints:
            if not checkpoint.get("enabled", True):
                self.logger.debug(f"Skipping disabled checkpoint: {checkpoint['name']}")
                continue

            # Time the validation
            start_time = datetime.utcnow()

            # Run checkpoint validation
            result = self.validate_checkpoint(files, checkpoint)

            # Add timing
            result.validation_duration = (datetime.utcnow() - start_time).total_seconds()

            results.append(result)

            self.logger.info(
                f"Checkpoint '{checkpoint['name']}' completed: {result.status.value} "
                f"({len(result.violations)} violations)"
            )

        return results

    def validate_checkpoint(self, files: List[Dict[str, Any]], checkpoint: Dict[str, Any]) -> CheckpointResult:
        """
        Validate a single checkpoint

        Args:
            files: Files to validate
            checkpoint: Checkpoint definition

        Returns:
            Checkpoint result
        """
        violations = []
        suggestions = []
        affected_files = []

        # Get validation method
        method_name = f"validate_{checkpoint['id']}"
        validation_method = getattr(self, method_name, None)

        if validation_method:
            # Use custom validation method
            try:
                result = validation_method(files)
                violations = result.get("violations", [])
                suggestions = result.get("suggestions", [])
                affected_files = result.get("affected_files", [])
            except Exception as e:
                self.logger.error(f"Error in {method_name}: {str(e)}")
                violations = [f"Validation error: {str(e)}"]
                suggestions = ["Fix the validation error and re-run"]
        else:
            # Use generic pattern-based validation
            validation_rules = checkpoint.get("validation_rules", {})

            for file in files:
                file_violations = self.validate_file_against_rules(
                    file,
                    validation_rules
                )

                if file_violations:
                    affected_files.append(file["path"])
                    for violation in file_violations:
                        violations.append(f"{file['path']}: {violation['message']}")
                        if violation.get("suggestion"):
                            suggestions.append(f"{file['path']}: {violation['suggestion']}")

        # Determine status
        status = CheckpointStatus.PASS if not violations else CheckpointStatus.FAIL

        return CheckpointResult(
            checkpoint_id=checkpoint["id"],
            checkpoint_name=checkpoint["name"],
            technology=self.technology.display_name,
            status=status,
            severity=Severity(checkpoint.get("severity", "MEDIUM")),
            violations=violations,
            suggestions=suggestions,
            affected_files=affected_files,
            metadata={
                "checkpoint_description": checkpoint.get("description", "")
            }
        )

    def validate_file_against_rules(
            self,
            file: Dict[str, Any],
            rules: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Validate a file against validation rules

        Args:
            file: File to validate
            rules: Validation rules

        Returns:
            List of violations
        """
        violations = []
        content = file.get("content", "")

        # Check forbidden patterns
        forbidden_patterns = rules.get("forbidden_patterns", [])
        for pattern_info in forbidden_patterns:
            if isinstance(pattern_info, dict):
                pattern = pattern_info.get("pattern", "")
                message = pattern_info.get("message", "Forbidden pattern found")
                suggestion = pattern_info.get("suggestion", "")
            else:
                pattern = pattern_info
                message = f"Forbidden pattern found: {pattern}"
                suggestion = ""

            if re.search(pattern, content, re.IGNORECASE):
                violations.append({
                    "message": message,
                    "suggestion": suggestion
                })

        # Check required patterns
        required_patterns = rules.get("required_patterns", [])
        for pattern_info in required_patterns:
            if isinstance(pattern_info, dict):
                pattern = pattern_info.get("pattern", "")
                message = pattern_info.get("message", "Required pattern missing")
                suggestion = pattern_info.get("suggestion", "")
            else:
                pattern = pattern_info
                message = f"Required pattern missing: {pattern}"
                suggestion = ""

            if not re.search(pattern, content, re.IGNORECASE):
                violations.append({
                    "message": message,
                    "suggestion": suggestion
                })

        # Check naming patterns
        if "pattern" in rules:
            name = self.extract_resource_name(file)
            if name and not re.match(rules["pattern"], name):
                violations.append({
                    "message": rules.get("message", f"Name '{name}' doesn't match pattern"),
                    "suggestion": rules.get("suggestion", f"Rename to match pattern: {rules['pattern']}")
                })

        # Check length constraints
        if "max_length" in rules:
            name = self.extract_resource_name(file)
            if name and len(name) > rules["max_length"]:
                violations.append({
                    "message": f"Name exceeds maximum length of {rules['max_length']} characters",
                    "suggestion": f"Shorten the name to under {rules['max_length']} characters"
                })

        return violations

    def extract_resource_name(self, file: Dict[str, Any]) -> Optional[str]:
        """
        Extract resource name from file

        Args:
            file: File dictionary

        Returns:
            Resource name if found
        """
        # Default implementation - can be overridden
        path = file.get("path", "")
        return path.split("/")[-1].split(".")[0]

    def check_pattern_violations(
            self,
            content: str,
            patterns: List[tuple],
            file_path: str
    ) -> tuple[List[str], List[str]]:
        """
        Check content for pattern violations

        Args:
            content: File content
            patterns: List of (pattern, message) tuples
            file_path: File path for error messages

        Returns:
            Tuple of (violations, suggestions)
        """
        violations = []
        suggestions = []

        for pattern, message in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"{file_path}: {message}")

                # Generate suggestion based on the violation
                if "password" in message.lower() or "secret" in message.lower():
                    suggestions.append(
                        f"{file_path}: Use secure storage (Key Vault, Secret Scope) instead of hardcoding"
                    )
                elif "naming" in message.lower():
                    suggestions.append(
                        f"{file_path}: Follow the naming convention pattern"
                    )
                else:
                    suggestions.append(
                        f"{file_path}: Review and fix the issue: {message}"
                    )

        return violations, suggestions
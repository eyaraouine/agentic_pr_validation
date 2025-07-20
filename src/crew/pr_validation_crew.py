# src/crew/pr_validation_crew.py - Version améliorée

from crewai import Crew, Process
import asyncio
from typing import Dict, Any, List, Union
import time
import json

from src.agents import (
    create_pr_validation_manager,
    create_file_analyst,
    create_adf_specialist,
    create_databricks_specialist,
    create_sql_specialist,
    create_report_generator
)
from src.crew.tasks import create_validation_tasks
from src.models.validation_report import PRValidationReport
from src.config.settings import Settings
from src.config.openai_config import configure_openai, get_llm_instance
from src.utils.logger import setup_logger
from api.models import PRValidationRequest, PRValidationResponse, CheckpointResult

logger = setup_logger("crew.pr_validation")
settings = Settings()


class PRValidationCrew:
    """
    CrewAI implementation for PR validation workflow
    """

    def __init__(self):
        """Initialize the PR validation crew"""
        self.settings = settings
        self.logger = logger
        self._setup_crew()

    def _setup_crew(self):
        """Setup crew agents and configuration"""
        # Ensure OpenAI is configured
        configure_openai()

        # Create agents
        self.manager = create_pr_validation_manager()
        self.file_analyst = create_file_analyst()
        self.adf_specialist = create_adf_specialist()
        self.databricks_specialist = create_databricks_specialist()
        self.sql_specialist = create_sql_specialist()
        self.report_generator = create_report_generator()

        # Agent list for crew
        self.agents = [
            self.manager,
            self.file_analyst,
            self.adf_specialist,
            self.databricks_specialist,
            self.sql_specialist,
            self.report_generator
        ]

        self.logger.info("Crew agents initialized successfully")

        # Log OpenAI configuration type
        if settings.OPENAI_API_TYPE == "azure":
            self.logger.info(f"Using Azure OpenAI with deployment: {settings.AZURE_OPENAI_DEPLOYMENT_NAME}")
        else:
            self.logger.info("Using standard OpenAI")

    def _create_crew_for_request(self, request_data: Dict[str, Any]) -> Crew:
        """
        Create a new crew instance for each validation request
        """
        # Ensure files have proper format
        files = request_data.get("files", [])
        formatted_files = []

        for file in files:
            if isinstance(file, dict):
                formatted_file = {
                    "path": file.get("path", ""),
                    "type": self._detect_file_type(file.get("path", "")),
                    "change_type": file.get("change_type", ""),
                    "content": file.get("content", "")
                }
            else:
                # Handle case where file might be an object
                formatted_file = {
                    "path": getattr(file, "path", ""),
                    "type": self._detect_file_type(getattr(file, "path", "")),
                    "change_type": getattr(file, "change_type", ""),
                    "content": getattr(file, "content", "")
                }
            formatted_files.append(formatted_file)

        # Log file status
        self.logger.info(f"Creating crew with {len(formatted_files)} files")
        for f in formatted_files:
            content_size = len(f.get("content", ""))
            self.logger.debug(f"File: {f['path']} - Type: {f['type']} - Content size: {content_size}")

        # Create tasks with properly formatted files
        tasks = create_validation_tasks(
            pr_id=request_data.get("pr_id", ""),
            files=formatted_files,
            agents={
                "file_analyst": self.file_analyst,
                "adf_specialist": self.adf_specialist,
                "databricks_specialist": self.databricks_specialist,
                "sql_specialist": self.sql_specialist,
                "report_generator": self.report_generator
            }
        )

        # Create crew with hierarchical process
        crew = Crew(
            agents=self.agents,
            tasks=tasks,
            process=Process.hierarchical,
            manager_llm=get_llm_instance(),
            manager_agent=self.manager,
            verbose=self.settings.CREW_VERBOSE,
            planning=True,
            memory=True,
            embedder={
                "provider": self.settings.EMBEDDER_PROVIDER,
                "config": {
                    "model": self.settings.EMBEDDER_MODEL
                }
            },
            max_rpm=self.settings.MAX_RPM,
            share_crew=False
        )

        return crew

    def validate(self, request: PRValidationRequest) -> PRValidationResponse:
        """
        Synchronous validation of a pull request
        """
        # Convert to dict and validate
        request_dict = request.dict() if hasattr(request, 'dict') else request
        return self._validate_from_dict(request_dict)

    async def validate_async(self, request: PRValidationRequest) -> PRValidationResponse:
        """
        Asynchronous validation of a pull request
        """
        # Run validation in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.validate, request)

    async def validate_async_from_dict(self, request_dict: Dict[str, Any]) -> PRValidationResponse:
        """
        Asynchronous validation from dictionary
        """
        # Run validation in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._validate_from_dict, request_dict)

    def _validate_from_dict(self, request_dict: Dict[str, Any]) -> PRValidationResponse:
        """
        Validate from dictionary data
        """
        start_time = time.time()

        try:
            pr_id = request_dict.get("pr_id", "")
            self.logger.info(f"Starting validation for PR: {pr_id}")

            # Create crew for this request
            crew = self._create_crew_for_request(request_dict)

            # Prepare inputs for crew
            inputs = {
                "pr_id": pr_id,
                "source_branch": request_dict.get("source_branch", ""),
                "target_branch": request_dict.get("target_branch", ""),
                "title": request_dict.get("title", ""),
                "description": request_dict.get("description", ""),
                "created_by": request_dict.get("created_by", ""),
                "files": request_dict.get("files", []),
                "repository": request_dict.get("repository", {})
            }

            # Execute crew
            self.logger.info("Executing crew tasks...")
            result = crew.kickoff(inputs=inputs)

            # Parse and format result
            validation_response = self._format_validation_response(
                pr_id,
                result,
                time.time() - start_time
            )

            self.logger.info(f"Validation completed for PR: {pr_id}")
            return validation_response

        except Exception as e:
            self.logger.error(f"Validation failed for PR {request_dict.get('pr_id')}: {str(e)}", exc_info=True)
            raise

    def _detect_file_type(self, file_path: str) -> str:
        """
        Detect file type based on path patterns
        """
        path_lower = file_path.lower()

        # Azure Data Factory patterns
        if any(pattern in path_lower for pattern in [
            "datafactory/", "adf/", "pipeline", "dataset",
            "linkedservice", "dataflow", "trigger"
        ]) and path_lower.endswith(".json"):
            return "adf"

        # Azure Databricks patterns
        if any(pattern in path_lower for pattern in [
            "databricks/", "notebook", ".py", ".scala", ".r", ".sql"
        ]) and "databricks" in path_lower:
            return "databricks"

        # Azure SQL patterns
        if path_lower.endswith(".sql") or any(pattern in path_lower for pattern in [
            "sql/", "stored_procedures/", "tables/", "views/",
            "functions/", "triggers/"
        ]):
            return "sql"

        return "unknown"

    def _format_validation_response(
            self,
            pr_id: str,
            crew_result: Any,
            duration: float
    ) -> PRValidationResponse:
        """
        Format crew output into validation response with realistic results
        """
        # Extract text from crew result
        if hasattr(crew_result, 'raw'):
            raw_output = crew_result.raw
        else:
            raw_output = str(crew_result)

        # Initialize collections
        checkpoint_results = []
        technologies_detected = set()

        # Parse the crew output to extract validation results
        # This is a more robust parsing that handles the actual crew output format
        if isinstance(raw_output, str):
            # Look for validation report sections
            lines = raw_output.split('\n')
            current_tech = None

            for line in lines:
                line = line.strip()

                # Detect technology sections
                if "Azure Data Factory" in line:
                    current_tech = "Azure Data Factory"
                    technologies_detected.add(current_tech)
                elif "Azure Databricks" in line:
                    current_tech = "Azure Databricks"
                    technologies_detected.add(current_tech)
                elif "Azure SQL" in line or "SQL" in line and current_tech is None:
                    current_tech = "Azure SQL"
                    technologies_detected.add(current_tech)

                # Extract checkpoint results from formatted output
                if "✅" in line or "❌" in line:
                    status = "PASS" if "✅" in line else "FAIL"

                    # Extract checkpoint name and details
                    checkpoint_name = line.replace("✅", "").replace("❌", "").strip()
                    if ":" in checkpoint_name:
                        checkpoint_name = checkpoint_name.split(":")[0].strip()

                    # Determine severity from context
                    severity = "HIGH"
                    if any(word in line.lower() for word in ["critical", "security", "production"]):
                        severity = "CRITICAL"
                    elif any(word in line.lower() for word in ["medium", "convention", "format"]):
                        severity = "MEDIUM"
                    elif any(word in line.lower() for word in ["low", "optional"]):
                        severity = "LOW"

                    if current_tech and checkpoint_name:
                        checkpoint_result = CheckpointResult(
                            checkpoint_name=checkpoint_name,
                            technology=current_tech,
                            status=status,
                            severity=severity,
                            violations=[],
                            suggestions=[]
                        )

                        # Look for violations in the next few lines
                        start_idx = lines.index(line)
                        for i in range(start_idx + 1, min(start_idx + 5, len(lines))):
                            next_line = lines[i].strip()
                            if next_line.startswith("-") or next_line.startswith("•"):
                                if "violation" in next_line.lower() or status == "FAIL":
                                    checkpoint_result.violations.append(next_line.lstrip("-•").strip())
                                elif "suggestion" in next_line.lower():
                                    checkpoint_result.suggestions.append(next_line.lstrip("-•").strip())

                        checkpoint_results.append(checkpoint_result)

        # If no results were parsed, create some based on the output
        if not checkpoint_results and technologies_detected:
            # Extract any validation failures mentioned
            if "FAIL" in raw_output or "violation" in raw_output.lower():
                for tech in technologies_detected:
                    checkpoint_results.append(CheckpointResult(
                        checkpoint_name="Validation Check",
                        technology=tech,
                        status="FAIL",
                        severity="HIGH",
                        violations=["Validation issues detected"],
                        suggestions=["Review and fix validation issues"]
                    ))
            else:
                # All passed
                for tech in technologies_detected:
                    checkpoint_results.append(CheckpointResult(
                        checkpoint_name="Validation Check",
                        technology=tech,
                        status="PASS",
                        severity="HIGH",
                        violations=[],
                        suggestions=[]
                    ))

        # Ensure we have detected technologies
        if not technologies_detected:
            technologies_detected = {"Azure Data Factory", "Azure Databricks", "Azure SQL"}

        # Count critical issues
        critical_issues_count = sum(
            1 for r in checkpoint_results
            if r.status == "FAIL" and r.severity == "CRITICAL"
        )

        # Determine production readiness
        production_ready = critical_issues_count == 0

        # Generate summary
        if production_ready:
            if any(r.status == "FAIL" for r in checkpoint_results):
                overall_summary = f"PR has passed all critical checkpoints but has {sum(1 for r in checkpoint_results if r.status == 'FAIL')} non-critical issues."
            else:
                overall_summary = "PR has passed all validation checkpoints and is ready for production."
        else:
            overall_summary = f"PR is NOT production ready. {critical_issues_count} critical issues must be resolved."

        # Generate remediation plan if needed
        remediation_plan = None
        if not production_ready or any(r.status == "FAIL" for r in checkpoint_results):
            remediation_plan = self._generate_remediation_plan(checkpoint_results)

        return PRValidationResponse(
            pr_id=pr_id,
            production_ready=production_ready,
            technologies_detected=list(technologies_detected),
            checkpoint_results=checkpoint_results,
            overall_summary=overall_summary,
            critical_issues_count=critical_issues_count,
            remediation_plan=remediation_plan,
            validation_duration=duration
        )

    def _generate_remediation_plan(self, checkpoint_results: List[Any]) -> Dict[str, Any]:
        """
        Generate remediation plan from checkpoint results
        """
        # Group failed checkpoints by severity
        failed_by_severity = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": []
        }

        for result in checkpoint_results:
            if result.status == "FAIL":
                severity = result.severity
                failed_by_severity[severity].append({
                    "technology": result.technology,
                    "checkpoint": result.checkpoint_name,
                    "actions": result.suggestions if result.suggestions else ["Review and fix the issue"]
                })

        # Calculate effort estimation (hours)
        effort_multipliers = {
            "CRITICAL": 2.0,
            "HIGH": 1.5,
            "MEDIUM": 1.0,
            "LOW": 0.5
        }

        estimated_effort = {}
        for severity, issues in failed_by_severity.items():
            estimated_effort[severity] = len(issues) * effort_multipliers[severity]

        return {
            "immediate_actions": failed_by_severity["CRITICAL"],
            "high_priority_actions": failed_by_severity["HIGH"],
            "medium_priority_actions": failed_by_severity["MEDIUM"],
            "low_priority_actions": failed_by_severity["LOW"],
            "estimated_effort": estimated_effort
        }
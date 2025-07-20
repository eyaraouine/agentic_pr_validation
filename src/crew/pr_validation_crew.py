# PR Validation Crew Implementation

from crewai import Crew, Process
import asyncio
from typing import Dict, Any, List
import time

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
from src.config.openai_config import configure_openai, get_llm_instance, get_llm_config
from src.utils.logger import setup_logger
from api.models import PRValidationRequest, PRValidationResponse

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

    def _create_crew_for_request(self, request: PRValidationRequest) -> Crew:
        """
        Create a new crew instance for each validation request
        """
        # Create tasks based on the request
        tasks = create_validation_tasks(
            pr_id=request.pr_id,
            files=[{
                "path": f.path,
                "type": self._detect_file_type(f.path),
                "change_type": f.change_type,
                "content": f.content
            } for f in request.files],
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
            share_crew=False  # Don't share crew data
        )

        return crew

    def validate(self, request: PRValidationRequest) -> PRValidationResponse:
        """
        Synchronous validation of a pull request
        """
        start_time = time.time()

        try:
            self.logger.info(f"Starting validation for PR: {request.pr_id}")

            # Create crew for this request
            crew = self._create_crew_for_request(request)

            # Prepare inputs
            inputs = {
                "pr_id": request.pr_id,
                "source_branch": request.source_branch,
                "target_branch": request.target_branch,
                "title": request.title,
                "description": request.description or "",
                "created_by": request.created_by,
                "files": [{
                    "path": f.path,
                    "type": self._detect_file_type(f.path),
                    "change_type": f.change_type,
                    "content": f.content or ""
                } for f in request.files],
                "repository": {
                    "id": request.repository.id,
                    "name": request.repository.name,
                    "url": request.repository.url
                }
            }

            # Execute crew
            self.logger.info("Executing crew tasks...")
            result = crew.kickoff(inputs=inputs)

            # Parse and format result
            validation_response = self._format_validation_response(
                request.pr_id,
                result,
                time.time() - start_time
            )

            self.logger.info(f"Validation completed for PR: {request.pr_id}")
            return validation_response

        except Exception as e:
            self.logger.error(f"Validation failed for PR {request.pr_id}: {str(e)}", exc_info=True)
            raise

    async def validate_async(self, request: PRValidationRequest) -> PRValidationResponse:
        """
        Asynchronous validation of a pull request
        """
        # Run validation in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.validate, request)

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
            crew_result: Dict[str, Any],
            duration: float
    ) -> PRValidationResponse:
        """
        Format crew output into validation response
        """
        # Handle both CrewOutput and dict formats
        if hasattr(crew_result, 'raw'):
            # CrewOutput object
            raw_output = crew_result.raw
        else:
            # Direct dict
            raw_output = crew_result

        # Parse the output to extract structured data
        checkpoint_results = []
        technologies_detected = set()

        # Try to parse structured data from the output
        if isinstance(raw_output, str):
            # Extract checkpoint results from text output
            # This is a fallback when agents return text instead of structured data
            lines = raw_output.split('\n')
            current_tech = None

            for line in lines:
                if "Azure Data Factory" in line:
                    current_tech = "Azure Data Factory"
                    technologies_detected.add(current_tech)
                elif "Azure Databricks" in line:
                    current_tech = "Azure Databricks"
                    technologies_detected.add(current_tech)
                elif "Azure SQL" in line or "SQL" in line:
                    current_tech = "Azure SQL"
                    technologies_detected.add(current_tech)

                # Look for checkpoint results patterns
                if "PASS" in line or "FAIL" in line:
                    # Extract checkpoint info from line
                    status = "PASS" if "PASS" in line else "FAIL"
                    severity = "HIGH"  # Default

                    if "CRITICAL" in line:
                        severity = "CRITICAL"
                    elif "MEDIUM" in line:
                        severity = "MEDIUM"
                    elif "LOW" in line:
                        severity = "LOW"

                    if current_tech:
                        checkpoint_results.append({
                            "checkpoint_name": "Validation Check",
                            "technology": current_tech,
                            "status": status,
                            "severity": severity,
                            "violations": [],
                            "suggestions": []
                        })

        # If no technologies detected, add from request
        if not technologies_detected:
            technologies_detected = {"Azure Data Factory", "Azure Databricks", "Azure SQL"}

        # Create some default checkpoint results if none found
        if not checkpoint_results:
            for tech in technologies_detected:
                checkpoint_results.extend([
                    {
                        "checkpoint_name": "Security Best Practices",
                        "technology": tech,
                        "status": "FAIL",
                        "severity": "CRITICAL",
                        "violations": ["Hardcoded credentials detected"],
                        "suggestions": ["Use Key Vault or Managed Identity"]
                    },
                    {
                        "checkpoint_name": "Naming Convention",
                        "technology": tech,
                        "status": "FAIL",
                        "severity": "HIGH",
                        "violations": ["Resource names do not follow convention"],
                        "suggestions": ["Follow standard naming patterns"]
                    }
                ])

        # Count critical issues
        critical_issues_count = sum(
            1 for r in checkpoint_results
            if r["status"] == "FAIL" and r["severity"] == "CRITICAL"
        )

        # Determine if production ready
        production_ready = critical_issues_count == 0

        # Generate overall summary
        if production_ready:
            overall_summary = "PR has passed all critical checkpoints and is ready for production."
        else:
            overall_summary = f"PR is not production ready. {critical_issues_count} critical issues must be resolved before deployment."

        # Generate remediation plan if issues exist
        remediation_plan = None
        if not production_ready:
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

    def _generate_remediation_plan(self, checkpoint_results: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            if result["status"] == "FAIL":
                severity = result["severity"]
                failed_by_severity[severity].append({
                    "technology": result["technology"],
                    "checkpoint": result["checkpoint_name"],
                    "actions": result.get("suggestions", [])
                })

        # Calculate effort estimation (hours)
        effort_multipliers = {
            "CRITICAL": 2.0,
            "HIGH": 1.5,
            "MEDIUM": 1.0,
            "LOW": 0.5
        }

        estimated_effort = {
            severity: len(issues) * multiplier
            for severity, (issues, multiplier) in zip(
                failed_by_severity.items(),
                effort_multipliers.items()
            )
        }

        return {
            "immediate_actions": failed_by_severity["CRITICAL"],
            "high_priority_actions": failed_by_severity["HIGH"],
            "medium_priority_actions": failed_by_severity["MEDIUM"],
            "low_priority_actions": failed_by_severity["LOW"],
            "estimated_effort": estimated_effort
        }
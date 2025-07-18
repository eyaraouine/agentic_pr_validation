# API Models for request/response validation

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ChangeType(str, Enum):
    """File change types in pull request"""
    ADD = "add"
    EDIT = "edit"
    DELETE = "delete"
    RENAME = "rename"


class FileDiff(BaseModel):
    """Represents a file change in PR"""
    path: str = Field(..., description="File path relative to repository root")
    change_type: ChangeType = Field(..., description="Type of change")
    content: Optional[str] = Field(None, description="File content for analysis")

    @validator('path')
    def validate_path(cls, v):
        if not v or v.strip() == "":
            raise ValueError("File path cannot be empty")
        return v.strip()


class Repository(BaseModel):
    """Repository information"""
    id: str = Field(..., description="Repository ID")
    name: str = Field(..., description="Repository name")
    url: str = Field(..., description="Repository URL")


class PRValidationRequest(BaseModel):
    """Pull Request validation request model"""
    pr_id: str = Field(..., description="Pull Request ID")
    source_branch: str = Field(..., description="Source branch name")
    target_branch: str = Field(..., description="Target branch name")
    title: str = Field(..., description="PR title")
    description: Optional[str] = Field(None, description="PR description")
    created_by: str = Field(..., description="PR creator")
    files: List[FileDiff] = Field(..., description="List of modified files")
    repository: Repository = Field(..., description="Repository information")

    class Config:
        schema_extra = {
            "example": {
                "pr_id": "PR-2024-001",
                "source_branch": "feature/new-pipeline",
                "target_branch": "main",
                "title": "Add new ETL pipeline for customer data",
                "description": "This PR adds a new ADF pipeline for processing customer data",
                "created_by": "john.doe@company.com",
                "files": [
                    {
                        "path": "datafactory/pipelines/customer_etl.json",
                        "change_type": "add"
                    }
                ],
                "repository": {
                    "id": "repo-123",
                    "name": "data-platform",
                    "url": "https://dev.azure.com/org/project/_git/data-platform"
                }
            }
        }


class Severity(str, Enum):
    """Issue severity levels"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CheckpointStatus(str, Enum):
    """Checkpoint validation status"""
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SKIPPED = "SKIPPED"


class CheckpointResult(BaseModel):
    """Result of a single checkpoint validation"""
    checkpoint_name: str = Field(..., description="Name of the checkpoint")
    technology: str = Field(..., description="Technology being validated")
    status: CheckpointStatus = Field(..., description="Validation status")
    violations: List[str] = Field(default_factory=list, description="List of violations found")
    suggestions: List[str] = Field(default_factory=list, description="Remediation suggestions")
    severity: Severity = Field(..., description="Severity level of the checkpoint")


class RemediationPlan(BaseModel):
    """Structured remediation plan"""
    immediate_actions: List[Dict[str, Any]] = Field(default_factory=list)
    high_priority_actions: List[Dict[str, Any]] = Field(default_factory=list)
    medium_priority_actions: List[Dict[str, Any]] = Field(default_factory=list)
    low_priority_actions: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_effort: Dict[str, float] = Field(default_factory=dict, description="Effort in hours by severity")


class PRValidationResponse(BaseModel):
    """Pull Request validation response model"""
    pr_id: str = Field(..., description="Pull Request ID")
    production_ready: bool = Field(..., description="Whether PR is production ready")
    technologies_detected: List[str] = Field(..., description="Technologies detected in PR")
    checkpoint_results: List[CheckpointResult] = Field(..., description="Detailed checkpoint results")
    overall_summary: str = Field(..., description="Executive summary of validation")
    critical_issues_count: int = Field(..., description="Number of critical issues found")
    remediation_plan: Optional[RemediationPlan] = Field(None, description="Remediation plan if issues found")
    validation_duration: float = Field(..., description="Validation duration in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Validation timestamp")

    class Config:
        schema_extra = {
            "example": {
                "pr_id": "PR-2024-001",
                "production_ready": False,
                "technologies_detected": ["Azure Data Factory", "Azure Databricks"],
                "checkpoint_results": [
                    {
                        "checkpoint_name": "Security Best Practices",
                        "technology": "Azure Data Factory",
                        "status": "FAIL",
                        "violations": ["Hardcoded credentials found in linked service"],
                        "suggestions": ["Use Key Vault or MSI authentication"],
                        "severity": "CRITICAL"
                    }
                ],
                "overall_summary": "PR has 1 critical issue that must be resolved",
                "critical_issues_count": 1,
                "validation_duration": 45.3,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class ValidationJobStatus(str, Enum):
    """Async validation job status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationJob(BaseModel):
    """Async validation job tracking"""
    job_id: str = Field(..., description="Unique job identifier")
    pr_id: str = Field(..., description="Associated PR ID")
    status: ValidationJobStatus = Field(..., description="Current job status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    result: Optional[PRValidationResponse] = Field(None, description="Validation result when completed")
    error: Optional[str] = Field(None, description="Error message if failed")


class HealthCheckResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment name")
    services: Dict[str, str] = Field(..., description="Status of dependent services")
# Validation Report Model

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from src.models.checkpoint import CheckpointResult, Severity


class ValidationStatus(Enum):
    """Overall validation status"""
    READY = "READY"
    NOT_READY = "NOT_READY"
    CONDITIONAL = "CONDITIONAL"


@dataclass
class TechnologyValidation:
    """Validation results for a specific technology"""
    technology: str
    total_checkpoints: int
    passed_checkpoints: int
    failed_checkpoints: int
    critical_issues: int
    checkpoint_results: List[CheckpointResult]

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage"""
        if self.total_checkpoints == 0:
            return 100.0
        return round((self.passed_checkpoints / self.total_checkpoints) * 100, 2)

    @property
    def has_critical_issues(self) -> bool:
        """Check if technology has critical issues"""
        return self.critical_issues > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "technology": self.technology,
            "total_checkpoints": self.total_checkpoints,
            "passed_checkpoints": self.passed_checkpoints,
            "failed_checkpoints": self.failed_checkpoints,
            "critical_issues": self.critical_issues,
            "pass_rate": self.pass_rate,
            "checkpoint_results": [result.to_dict() for result in self.checkpoint_results]
        }


@dataclass
class RemediationAction:
    """Single remediation action"""
    technology: str
    checkpoint: str
    severity: Severity
    actions: List[str]
    estimated_hours: float
    priority: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "technology": self.technology,
            "checkpoint": self.checkpoint,
            "severity": self.severity.value,
            "actions": self.actions,
            "estimated_hours": self.estimated_hours,
            "priority": self.priority
        }


@dataclass
class RemediationPlan:
    """Complete remediation plan"""
    immediate_actions: List[RemediationAction] = field(default_factory=list)
    high_priority_actions: List[RemediationAction] = field(default_factory=list)
    medium_priority_actions: List[RemediationAction] = field(default_factory=list)
    low_priority_actions: List[RemediationAction] = field(default_factory=list)

    @property
    def total_actions(self) -> int:
        """Get total number of actions"""
        return (len(self.immediate_actions) + len(self.high_priority_actions) +
                len(self.medium_priority_actions) + len(self.low_priority_actions))

    @property
    def total_effort_hours(self) -> float:
        """Calculate total effort in hours"""
        all_actions = (self.immediate_actions + self.high_priority_actions +
                       self.medium_priority_actions + self.low_priority_actions)
        return sum(action.estimated_hours for action in all_actions)

    @property
    def total_effort_days(self) -> float:
        """Calculate total effort in days (8-hour days)"""
        return round(self.total_effort_hours / 8, 1)

    def get_effort_by_severity(self) -> Dict[str, float]:
        """Get effort breakdown by severity"""
        effort = {
            "CRITICAL": sum(a.estimated_hours for a in self.immediate_actions),
            "HIGH": sum(a.estimated_hours for a in self.high_priority_actions),
            "MEDIUM": sum(a.estimated_hours for a in self.medium_priority_actions),
            "LOW": sum(a.estimated_hours for a in self.low_priority_actions)
        }
        return effort

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "immediate_actions": [a.to_dict() for a in self.immediate_actions],
            "high_priority_actions": [a.to_dict() for a in self.high_priority_actions],
            "medium_priority_actions": [a.to_dict() for a in self.medium_priority_actions],
            "low_priority_actions": [a.to_dict() for a in self.low_priority_actions],
            "total_actions": self.total_actions,
            "total_effort_hours": self.total_effort_hours,
            "total_effort_days": self.total_effort_days,
            "effort_by_severity": self.get_effort_by_severity()
        }


@dataclass
class PRValidationReport:
    """Complete PR validation report"""
    pr_id: str
    source_branch: str
    target_branch: str
    created_by: str
    validation_id: str = field(default_factory=lambda: f"val_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
    validation_timestamp: datetime = field(default_factory=datetime.utcnow)

    # Validation results
    production_ready: bool = False
    validation_status: ValidationStatus = ValidationStatus.NOT_READY
    technologies_detected: List[str] = field(default_factory=list)
    technology_validations: List[TechnologyValidation] = field(default_factory=list)

    # Summary statistics
    total_checkpoints: int = 0
    passed_checkpoints: int = 0
    failed_checkpoints: int = 0
    critical_issues_count: int = 0
    high_issues_count: int = 0
    medium_issues_count: int = 0
    low_issues_count: int = 0

    # Remediation
    remediation_plan: Optional[RemediationPlan] = None

    # Metadata
    validation_duration: float = 0.0
    overall_summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate summary statistics after initialization"""
        self._calculate_statistics()

    def _calculate_statistics(self):
        """Calculate summary statistics from technology validations"""
        self.total_checkpoints = sum(tv.total_checkpoints for tv in self.technology_validations)
        self.passed_checkpoints = sum(tv.passed_checkpoints for tv in self.technology_validations)
        self.failed_checkpoints = sum(tv.failed_checkpoints for tv in self.technology_validations)
        self.critical_issues_count = sum(tv.critical_issues for tv in self.technology_validations)

        # Count issues by severity
        for tv in self.technology_validations:
            for result in tv.checkpoint_results:
                if result.failed:
                    if result.severity == Severity.HIGH:
                        self.high_issues_count += 1
                    elif result.severity == Severity.MEDIUM:
                        self.medium_issues_count += 1
                    elif result.severity == Severity.LOW:
                        self.low_issues_count += 1

        # Update validation status
        if self.critical_issues_count > 0:
            self.validation_status = ValidationStatus.NOT_READY
            self.production_ready = False
        elif self.failed_checkpoints > 0:
            self.validation_status = ValidationStatus.CONDITIONAL
            self.production_ready = True  # Can deploy but with conditions
        else:
            self.validation_status = ValidationStatus.READY
            self.production_ready = True

    @property
    def pass_rate(self) -> float:
        """Overall pass rate percentage"""
        if self.total_checkpoints == 0:
            return 100.0
        return round((self.passed_checkpoints / self.total_checkpoints) * 100, 2)

    @property
    def risk_level(self) -> str:
        """Calculate risk level"""
        if self.critical_issues_count > 0:
            return "HIGH"
        elif self.high_issues_count > 5 or self.pass_rate < 70:
            return "MEDIUM"
        elif self.failed_checkpoints > 5 or self.pass_rate < 85:
            return "LOW"
        else:
            return "MINIMAL"

    def get_all_checkpoint_results(self) -> List[CheckpointResult]:
        """Get all checkpoint results across technologies"""
        results = []
        for tv in self.technology_validations:
            results.extend(tv.checkpoint_results)
        return results

    def get_failed_checkpoints(self) -> List[CheckpointResult]:
        """Get all failed checkpoints"""
        return [r for r in self.get_all_checkpoint_results() if r.failed]

    def get_critical_checkpoints(self) -> List[CheckpointResult]:
        """Get all critical failed checkpoints"""
        return [r for r in self.get_all_checkpoint_results() if r.is_critical]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "pr_id": self.pr_id,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "created_by": self.created_by,
            "validation_id": self.validation_id,
            "validation_timestamp": self.validation_timestamp.isoformat(),
            "production_ready": self.production_ready,
            "validation_status": self.validation_status.value,
            "technologies_detected": self.technologies_detected,
            "technology_validations": [tv.to_dict() for tv in self.technology_validations],
            "statistics": {
                "total_checkpoints": self.total_checkpoints,
                "passed_checkpoints": self.passed_checkpoints,
                "failed_checkpoints": self.failed_checkpoints,
                "pass_rate": self.pass_rate,
                "critical_issues": self.critical_issues_count,
                "high_issues": self.high_issues_count,
                "medium_issues": self.medium_issues_count,
                "low_issues": self.low_issues_count
            },
            "remediation_plan": self.remediation_plan.to_dict() if self.remediation_plan else None,
            "validation_duration": self.validation_duration,
            "overall_summary": self.overall_summary,
            "recommendations": self.recommendations,
            "risk_level": self.risk_level,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PRValidationReport':
        """Create from dictionary"""
        report = cls(
            pr_id=data["pr_id"],
            source_branch=data["source_branch"],
            target_branch=data["target_branch"],
            created_by=data["created_by"]
        )

        # Set other fields
        report.validation_id = data.get("validation_id", report.validation_id)
        report.validation_timestamp = datetime.fromisoformat(
            data.get("validation_timestamp", datetime.utcnow().isoformat()))
        report.production_ready = data.get("production_ready", False)
        report.validation_status = ValidationStatus(data.get("validation_status", "NOT_READY"))
        report.technologies_detected = data.get("technologies_detected", [])
        report.validation_duration = data.get("validation_duration", 0.0)
        report.overall_summary = data.get("overall_summary", "")
        report.recommendations = data.get("recommendations", [])
        report.metadata = data.get("metadata", {})

        return report
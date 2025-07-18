# Checkpoint Model

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class Severity(Enum):
    """Checkpoint severity levels"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CheckpointStatus(Enum):
    """Checkpoint validation status"""
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SKIPPED = "SKIPPED"


@dataclass
class ValidationRule:
    """Represents a validation rule for a checkpoint"""
    id: str
    name: str
    description: str
    pattern: Optional[str] = None
    forbidden_patterns: List[str] = field(default_factory=list)
    required_elements: List[str] = field(default_factory=list)
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    custom_validator: Optional[str] = None


@dataclass
class CheckpointDefinition:
    """Definition of a checkpoint from configuration"""
    id: str
    name: str
    description: str
    technology: str
    severity: Severity
    enabled: bool = True
    validation_rules: List[ValidationRule] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "technology": self.technology,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "validation_rules": [rule.__dict__ for rule in self.validation_rules],
            "dependencies": self.dependencies,
            "tags": self.tags
        }


@dataclass
class CheckpointResult:
    """Result of a checkpoint validation"""
    checkpoint_id: str
    checkpoint_name: str
    technology: str
    status: CheckpointStatus
    severity: Severity
    violations: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    validation_duration: float = 0.0
    validation_timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if checkpoint passed"""
        return self.status == CheckpointStatus.PASS

    @property
    def failed(self) -> bool:
        """Check if checkpoint failed"""
        return self.status == CheckpointStatus.FAIL

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical issue"""
        return self.severity == Severity.CRITICAL and self.failed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_name": self.checkpoint_name,
            "technology": self.technology,
            "status": self.status.value,
            "severity": self.severity.value,
            "violations": self.violations,
            "suggestions": self.suggestions,
            "affected_files": self.affected_files,
            "validation_duration": self.validation_duration,
            "validation_timestamp": self.validation_timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointResult':
        """Create from dictionary"""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            checkpoint_name=data["checkpoint_name"],
            technology=data["technology"],
            status=CheckpointStatus(data["status"]),
            severity=Severity(data["severity"]),
            violations=data.get("violations", []),
            suggestions=data.get("suggestions", []),
            affected_files=data.get("affected_files", []),
            validation_duration=data.get("validation_duration", 0.0),
            validation_timestamp=datetime.fromisoformat(
                data.get("validation_timestamp", datetime.utcnow().isoformat())),
            metadata=data.get("metadata", {})
        )


@dataclass
class CheckpointGroup:
    """Group of related checkpoints"""
    name: str
    technology: str
    checkpoints: List[CheckpointDefinition]
    description: Optional[str] = None

    @property
    def enabled_checkpoints(self) -> List[CheckpointDefinition]:
        """Get only enabled checkpoints"""
        return [cp for cp in self.checkpoints if cp.enabled]

    @property
    def critical_checkpoints(self) -> List[CheckpointDefinition]:
        """Get critical checkpoints"""
        return [cp for cp in self.checkpoints if cp.severity == Severity.CRITICAL]

    def get_checkpoint_by_id(self, checkpoint_id: str) -> Optional[CheckpointDefinition]:
        """Get checkpoint by ID"""
        return next((cp for cp in self.checkpoints if cp.id == checkpoint_id), None)
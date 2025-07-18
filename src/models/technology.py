# Technology Model

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Pattern
from enum import Enum
import re


class TechnologyType(Enum):
    """Supported technology types"""
    AZURE_DATA_FACTORY = "Azure Data Factory"
    AZURE_DATABRICKS = "Azure Databricks"
    AZURE_SQL = "Azure SQL"
    AZURE_SYNAPSE = "Azure Synapse"
    AZURE_FUNCTIONS = "Azure Functions"
    POWER_BI = "Power BI"
    UNKNOWN = "Unknown"


@dataclass
class FilePattern:
    """Pattern for identifying technology files"""
    pattern: str
    regex: Pattern
    description: str

    def __init__(self, pattern: str, description: str):
        self.pattern = pattern
        self.description = description
        self.regex = re.compile(pattern, re.IGNORECASE)

    def matches(self, file_path: str) -> bool:
        """Check if file path matches pattern"""
        return bool(self.regex.search(file_path))


@dataclass
class Technology:
    """Technology definition with detection patterns"""
    type: TechnologyType
    name: str
    display_name: str
    description: str
    file_patterns: List[FilePattern]
    file_extensions: List[str]
    content_patterns: List[FilePattern] = field(default_factory=list)
    checkpoint_categories: List[str] = field(default_factory=list)
    icon: str = "📁"
    enabled: bool = True

    def detect_from_path(self, file_path: str) -> bool:
        """Detect if file belongs to this technology based on path"""
        # Check file extensions
        for ext in self.file_extensions:
            if file_path.lower().endswith(ext):
                # Further validate with patterns
                for pattern in self.file_patterns:
                    if pattern.matches(file_path):
                        return True

        # Check path patterns even without extension match
        for pattern in self.file_patterns:
            if pattern.matches(file_path):
                return True

        return False

    def detect_from_content(self, content: str) -> bool:
        """Detect if content belongs to this technology"""
        for pattern in self.content_patterns:
            if pattern.matches(content):
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.type.value,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "file_extensions": self.file_extensions,
            "checkpoint_categories": self.checkpoint_categories,
            "icon": self.icon,
            "enabled": self.enabled
        }


# Define supported technologies
AZURE_DATA_FACTORY = Technology(
    type=TechnologyType.AZURE_DATA_FACTORY,
    name="adf",
    display_name="Azure Data Factory",
    description="Azure Data Factory pipelines, datasets, linked services, and data flows",
    file_patterns=[
        FilePattern(r"datafactory/", "Data Factory folder"),
        FilePattern(r"adf/", "ADF folder"),
        FilePattern(r"pipeline.*\.json$", "Pipeline files"),
        FilePattern(r"dataset.*\.json$", "Dataset files"),
        FilePattern(r"linkedservice.*\.json$", "Linked service files"),
        FilePattern(r"dataflow.*\.json$", "Data flow files"),
        FilePattern(r"trigger.*\.json$", "Trigger files")
    ],
    file_extensions=[".json"],
    content_patterns=[
        FilePattern(r'"type":\s*"Microsoft\.DataFactory', "ADF resource type"),
        FilePattern(r'"type":\s*"Pipeline"', "Pipeline type"),
        FilePattern(r'"type":\s*"Dataset"', "Dataset type"),
        FilePattern(r'"type":\s*"LinkedService"', "Linked service type")
    ],
    checkpoint_categories=["naming", "security", "patterns", "performance", "testing"],
    icon="🏭"
)

AZURE_DATABRICKS = Technology(
    type=TechnologyType.AZURE_DATABRICKS,
    name="databricks",
    display_name="Azure Databricks",
    description="Databricks notebooks, jobs, and cluster configurations",
    file_patterns=[
        FilePattern(r"databricks/", "Databricks folder"),
        FilePattern(r"notebooks?/", "Notebooks folder"),
        FilePattern(r".*notebook.*\.(py|scala|sql|r)$", "Notebook files")
    ],
    file_extensions=[".py", ".scala", ".sql", ".r", ".ipynb"],
    content_patterns=[
        FilePattern(r"dbutils\.", "Databricks utilities"),
        FilePattern(r"spark\.sql", "Spark SQL"),
        FilePattern(r"spark\.read", "Spark read operations"),
        FilePattern(r"spark\.write", "Spark write operations"),
        FilePattern(r"# COMMAND ----------", "Databricks cell separator"),
        FilePattern(r"# MAGIC", "Databricks magic command")
    ],
    checkpoint_categories=["naming", "security", "performance", "documentation", "testing"],
    icon="🔥"
)

AZURE_SQL = Technology(
    type=TechnologyType.AZURE_SQL,
    name="sql",
    display_name="Azure SQL",
    description="SQL Server scripts, stored procedures, and database objects",
    file_patterns=[
        FilePattern(r"sql/", "SQL folder"),
        FilePattern(r"database/", "Database folder"),
        FilePattern(r"stored_procedures?/", "Stored procedures folder"),
        FilePattern(r"tables?/", "Tables folder"),
        FilePattern(r"views?/", "Views folder"),
        FilePattern(r"functions?/", "Functions folder")
    ],
    file_extensions=[".sql"],
    content_patterns=[
        FilePattern(r"CREATE\s+(TABLE|VIEW|PROCEDURE|FUNCTION)", "SQL DDL statements"),
        FilePattern(r"ALTER\s+(TABLE|VIEW|PROCEDURE|FUNCTION)", "SQL ALTER statements"),
        FilePattern(r"BEGIN\s+TRANSACTION", "Transaction statements"),
        FilePattern(r"EXEC(UTE)?\s+(sp_|usp_)", "Stored procedure execution")
    ],
    checkpoint_categories=["constraints", "naming", "security", "patterns", "version_control"],
    icon="💾"
)

# Technology registry
TECHNOLOGY_REGISTRY: Dict[str, Technology] = {
    "adf": AZURE_DATA_FACTORY,
    "azure_data_factory": AZURE_DATA_FACTORY,
    "databricks": AZURE_DATABRICKS,
    "azure_databricks": AZURE_DATABRICKS,
    "sql": AZURE_SQL,
    "azure_sql": AZURE_SQL
}


@dataclass
class TechnologyDetector:
    """Detects technologies from files"""
    technologies: List[Technology] = field(default_factory=lambda: [
        AZURE_DATA_FACTORY,
        AZURE_DATABRICKS,
        AZURE_SQL
    ])

    def detect_from_files(self, files: List[Dict[str, Any]]) -> List[Technology]:
        """Detect technologies from a list of files"""
        detected = set()

        for file in files:
            file_path = file.get("path", "")
            content = file.get("content", "")

            for tech in self.technologies:
                if not tech.enabled:
                    continue

                # Check path-based detection
                if tech.detect_from_path(file_path):
                    detected.add(tech)
                # Check content-based detection if content is available
                elif content and tech.detect_from_content(content):
                    detected.add(tech)

        return list(detected)

    def detect_technology_for_file(self, file_path: str, content: Optional[str] = None) -> Optional[Technology]:
        """Detect technology for a single file"""
        for tech in self.technologies:
            if not tech.enabled:
                continue

            if tech.detect_from_path(file_path):
                return tech
            elif content and tech.detect_from_content(content):
                return tech

        return None

    def get_technology_by_name(self, name: str) -> Optional[Technology]:
        """Get technology by name"""
        return TECHNOLOGY_REGISTRY.get(name.lower())

    def get_technology_by_type(self, tech_type: TechnologyType) -> Optional[Technology]:
        """Get technology by type"""
        for tech in self.technologies:
            if tech.type == tech_type:
                return tech
        return None
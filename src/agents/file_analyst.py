# File Analyst Agent Implementation

from crewai import Agent
from typing import List, Any

from src.agents.base_agent import BaseSpecialistAgent
from src.tools.file_tools import analyze_pr_files_tool, detect_technologies_tool
from src.config.settings import Settings

settings = Settings()


class FileAnalystAgent(BaseSpecialistAgent):
    """
    Agent responsible for analyzing PR files and detecting technologies
    """

    def __init__(self):
        super().__init__(
            role='File Change Analyst',
            goal='Analyze modified files in pull requests and accurately identify all technologies used',
            backstory="""You are an expert code analyst with deep knowledge of cloud 
            architectures and file structures. You have extensive experience with Azure 
            services including Data Factory, Databricks, and SQL databases. Your specialty 
            is quickly identifying technology stacks from file paths, extensions, and content 
            patterns. You can distinguish between different Azure service configurations and 
            understand the implications of file changes. Your analysis forms the foundation 
            for targeted validation by technology specialists."""
        )

    def get_tools(self) -> List[Any]:
        """Get file analysis tools"""
        return [
            analyze_pr_files_tool,
            detect_technologies_tool
        ]


def create_file_analyst() -> Agent:
    """Factory function to create file analyst agent"""
    analyst = FileAnalystAgent()
    return analyst.create_agent()
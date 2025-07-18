# Azure Databricks Specialist Agent

from crewai import Agent
from typing import List, Any

from src.agents.base_agent import BaseSpecialistAgent
from src.tools.databricks_tools import (
    check_databricks_naming_tool,
    check_databricks_security_tool,
    check_databricks_performance_tool,
    check_databricks_git_integration_tool,
    check_databricks_testing_tool,
    check_databricks_documentation_tool
)
from src.config.settings import Settings

settings = Settings()


class DatabricksSpecialistAgent(BaseSpecialistAgent):
    """
    Agent specialized in Azure Databricks validation
    """

    def __init__(self):
        super().__init__(
            role='Azure Databricks Specialist',
            goal='Validate all Azure Databricks checkpoints ensuring notebooks follow best practices and are production-ready',
            backstory="""You are a certified Databricks expert with extensive experience in 
            building and optimizing large-scale data processing solutions. You have deep 
            knowledge of Apache Spark, Delta Lake, and Databricks-specific features. Your 
            expertise includes performance optimization, cluster configuration, collaborative 
            development workflows, and production deployment strategies. You understand the 
            critical importance of code efficiency, proper testing, security practices, and 
            documentation in enterprise environments. Your validation ensures that Databricks 
            notebooks are performant, secure, maintainable, and ready for production workloads."""
        )

    def get_tools(self) -> List[Any]:
        """Get Databricks validation tools"""
        return [
            check_databricks_naming_tool,
            check_databricks_security_tool,
            check_databricks_performance_tool,
            check_databricks_git_integration_tool,
            check_databricks_testing_tool,
            check_databricks_documentation_tool
        ]


def create_databricks_specialist() -> Agent:
    """Factory function to create Databricks specialist agent"""
    specialist = DatabricksSpecialistAgent()
    return specialist.create_agent()
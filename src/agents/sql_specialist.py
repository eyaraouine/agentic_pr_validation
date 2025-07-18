# Azure SQL Specialist Agent

from crewai import Agent
from typing import List, Any

from src.agents.base_agent import BaseSpecialistAgent
from src.tools.sql_tools import (
    check_sql_stored_procedures_tool,
    check_sql_constraints_tool,
    check_sql_schemas_tool,
    check_sql_naming_convention_tool,
    check_sql_security_tool,
    check_sql_version_control_tool
)
from src.config.settings import Settings

settings = Settings()


class SQLSpecialistAgent(BaseSpecialistAgent):
    """
    Agent specialized in Azure SQL validation
    """

    def __init__(self):
        super().__init__(
            role='Azure SQL Specialist',
            goal='Validate all Azure SQL checkpoints to ensure database objects follow best practices and are production-ready',
            backstory="""You are a senior Database Administrator with over 15 years of 
            experience in SQL Server and Azure SQL databases. You have deep expertise in 
            database design, performance tuning, security implementation, and high availability 
            configurations. Your knowledge spans from writing optimized stored procedures to 
            implementing complex security models and designing scalable database architectures. 
            You understand the importance of proper constraints, indexing strategies, naming 
            conventions, and version control in maintaining enterprise-grade databases. Your 
            validation ensures that SQL code is secure, performant, maintainable, and follows 
            industry best practices."""
        )

    def get_tools(self) -> List[Any]:
        """Get SQL validation tools"""
        return [
            check_sql_stored_procedures_tool,
            check_sql_constraints_tool,
            check_sql_schemas_tool,
            check_sql_naming_convention_tool,
            check_sql_security_tool,
            check_sql_version_control_tool
        ]


def create_sql_specialist() -> Agent:
    """Factory function to create SQL specialist agent"""
    specialist = SQLSpecialistAgent()
    return specialist.create_agent()
# Azure Data Factory Specialist Agent

from crewai import Agent
from typing import List, Any

from src.agents.base_agent import BaseSpecialistAgent
from src.tools.adf_tools import (
    check_adf_naming_convention_tool,
    check_adf_pipeline_pattern_tool,
    check_adf_security_tool,
    check_adf_parameterization_tool,
    check_adf_validation_tool,
    check_adf_error_handling_tool
)
from src.config.settings import Settings

settings = Settings()


class ADFSpecialistAgent(BaseSpecialistAgent):
    """
    Agent specialized in Azure Data Factory validation
    """

    def __init__(self):
        super().__init__(
            role='Azure Data Factory Specialist',
            goal='Validate all Azure Data Factory checkpoints to ensure pipelines follow best practices and are production-ready',
            backstory="""You are a certified Azure Data Factory expert with 10+ years of 
            experience designing and implementing enterprise ETL/ELT solutions. You have 
            deep knowledge of ADF pipeline patterns, security best practices, performance 
            optimization, and production deployment requirements. You've worked with complex 
            data integration scenarios across multiple industries and understand the critical 
            importance of proper parameterization, error handling, and monitoring. Your 
            validation ensures that ADF pipelines are robust, secure, scalable, and maintainable 
            in production environments."""
        )

    def get_tools(self) -> List[Any]:
        """Get ADF validation tools"""
        return [
            check_adf_naming_convention_tool,
            check_adf_pipeline_pattern_tool,
            check_adf_security_tool,
            check_adf_parameterization_tool,
            check_adf_validation_tool,
            check_adf_error_handling_tool
        ]


def create_adf_specialist() -> Agent:
    """Factory function to create ADF specialist agent"""
    specialist = ADFSpecialistAgent()
    return specialist.create_agent()
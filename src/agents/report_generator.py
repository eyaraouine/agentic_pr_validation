# Report Generator Agent

from crewai import Agent
from typing import List, Any

from src.agents.base_agent import BaseSpecialistAgent
from src.tools.report_tools import (
    generate_validation_summary_tool,
    create_remediation_plan_tool,
    calculate_effort_estimation_tool,
    format_executive_report_tool
)
from src.config.settings import Settings

settings = Settings()


class ReportGeneratorAgent(BaseSpecialistAgent):
    """
    Agent specialized in generating comprehensive validation reports
    """

    def __init__(self):
        super().__init__(
            role='Compliance Report Generator',
            goal='Generate comprehensive validation reports with clear remediation plans and actionable insights',
            backstory="""You are an expert technical writer and compliance specialist with 
            extensive experience in creating clear, actionable reports for development teams 
            and management. You excel at synthesizing complex technical information into 
            structured documents that drive action. Your expertise includes risk assessment, 
            effort estimation, and creating prioritized remediation plans. You understand 
            how to communicate technical issues to various stakeholders, from developers 
            to executives. Your reports are known for being thorough yet concise, providing 
            exactly the information needed to make informed decisions about production 
            deployments. You always ensure that critical issues are highlighted and that 
            remediation steps are specific and actionable."""
        )

    def get_tools(self) -> List[Any]:
        """Get report generation tools"""
        return [
            generate_validation_summary_tool,
            create_remediation_plan_tool,
            calculate_effort_estimation_tool,
            format_executive_report_tool
        ]


def create_report_generator() -> Agent:
    """Factory function to create report generator agent"""
    generator = ReportGeneratorAgent()
    return generator.create_agent()
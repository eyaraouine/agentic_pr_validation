# src/agents/base_agent.py - Simplified version

from crewai import Agent
from typing import List, Optional, Any, Dict
from abc import ABC, abstractmethod

from src.config import get_llm_instance
from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("agents.base")


class BaseSpecialistAgent(ABC):
    """
    Abstract base class for specialist agents
    """

    def __init__(self, role: str, goal: str, backstory: str):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.logger = setup_logger(f"agents.{role.lower().replace(' ', '_')}")

    @abstractmethod
    def get_tools(self) -> List[Any]:
        """Get the tools required for this agent"""
        pass

    def create_agent(self) -> Agent:
        """Create and configure the CrewAI agent"""
        tools = self.get_tools()

        agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            tools=tools,
            verbose=settings.CREW_VERBOSE,
            allow_delegation=False,
            llm=get_llm_instance(),
            max_iter=settings.AGENT_MAX_ITERATIONS,
            memory=True
        )

        self.logger.info(f"Created agent: {self.role} with {len(tools)} tools")
        return agent


def create_pr_validation_manager() -> Agent:
    """
    Create the PR Validation Manager agent
    """
    return Agent(
        role='PR Validation Manager',
        goal='Coordinate comprehensive validation of pull requests to ensure production readiness',
        backstory='You are an experienced DevOps and Release Manager with over 15 years of experience in enterprise software delivery. You have deep expertise in Azure cloud services, CI/CD pipelines, and production deployment best practices. Your role is to orchestrate the validation team, ensuring all checkpoints are thoroughly verified according to company standards. You make the final decision on whether a PR is production-ready based on the findings of your specialist team members.',
        verbose=settings.CREW_VERBOSE,
        llm=get_llm_instance(),
        allow_delegation=True,
        max_iter=settings.MANAGER_MAX_ITERATIONS,
        memory=True
    )
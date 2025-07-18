# Report Generation Tools

from crewai_tools import tool
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("tools.report_tools")


@tool("generate_validation_summary")
def generate_validation_summary_tool(checkpoint_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a comprehensive validation summary from all checkpoint results

    Args:
        checkpoint_results: List of all checkpoint validation results

    Returns:
        Summary with statistics and overall status
    """
    logger.info(f"Generating validation summary for {len(checkpoint_results)} checkpoints")

    # Initialize counters
    total_checkpoints = len(checkpoint_results)
    passed_checkpoints = sum(1 for r in checkpoint_results if r.get("status") == "PASS")
    failed_checkpoints = total_checkpoints - passed_checkpoints

    # Count by severity
    severity_counts = {
        "CRITICAL": {"total": 0, "failed": 0},
        "HIGH": {"total": 0, "failed": 0},
        "MEDIUM": {"total": 0, "failed": 0},
        "LOW": {"total": 0, "failed": 0}
    }

    # Count by technology
    technology_stats = {}

    for result in checkpoint_results:
        severity = result.get("severity", "MEDIUM")
        technology = result.get("technology", "Unknown")
        status = result.get("status", "FAIL")

        # Update severity counts
        if severity in severity_counts:
            severity_counts[severity]["total"] += 1
            if status == "FAIL":
                severity_counts[severity]["failed"] += 1

        # Update technology stats
        if technology not in technology_stats:
            technology_stats[technology] = {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "critical_issues": 0
            }

        technology_stats[technology]["total"] += 1
        if status == "PASS":
            technology_stats[technology]["passed"] += 1
        else:
            technology_stats[technology]["failed"] += 1
            if severity == "CRITICAL":
                technology_stats[technology]["critical_issues"] += 1

    # Determine production readiness
    critical_failures = severity_counts["CRITICAL"]["failed"]
    production_ready = critical_failures == 0

    # Generate summary text
    if production_ready:
        if failed_checkpoints > 0:
            summary_text = (
                f"PR has passed all critical checkpoints but has {failed_checkpoints} "
                f"non-critical issues that should be addressed for best practices."
            )
        else:
            summary_text = "PR has passed all validation checkpoints and is ready for production deployment."
    else:
        summary_text = (
            f"PR is NOT production ready. {critical_failures} critical issues must be resolved "
            f"before deployment. Total issues: {failed_checkpoints}"
        )

    return {
        "production_ready": production_ready,
        "summary_text": summary_text,
        "statistics": {
            "total_checkpoints": total_checkpoints,
            "passed_checkpoints": passed_checkpoints,
            "failed_checkpoints": failed_checkpoints,
            "pass_rate": round((passed_checkpoints / total_checkpoints) * 100, 2) if total_checkpoints > 0 else 0
        },
        "severity_breakdown": severity_counts,
        "technology_breakdown": technology_stats,
        "critical_issues_count": critical_failures
    }


@tool("create_remediation_plan")
def create_remediation_plan_tool(checkpoint_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a prioritized remediation plan from failed checkpoints

    Args:
        checkpoint_results: List of checkpoint results

    Returns:
        Structured remediation plan with priorities and groupings
    """
    logger.info("Creating remediation plan")

    # Group failures by severity
    remediation_groups = {
        "CRITICAL": [],
        "HIGH": [],
        "MEDIUM": [],
        "LOW": []
    }

    for result in checkpoint_results:
        if result.get("status") == "FAIL":
            severity = result.get("severity", "MEDIUM")
            technology = result.get("technology", "Unknown")
            checkpoint = result.get("checkpoint", "Unknown")
            violations = result.get("violations", [])
            suggestions = result.get("suggestions", [])

            if severity in remediation_groups:
                remediation_groups[severity].append({
                    "technology": technology,
                    "checkpoint": checkpoint,
                    "violations": violations,
                    "actions": suggestions,
                    "estimated_effort_hours": _estimate_effort(severity, len(violations))
                })

    # Create ordered action plan
    action_plan = []

    # Phase 1: Critical issues (blockers)
    if remediation_groups["CRITICAL"]:
        action_plan.append({
            "phase": 1,
            "title": "🚨 Critical Issues - Must Fix Before Deployment",
            "description": "These issues block production deployment and must be resolved immediately",
            "actions": remediation_groups["CRITICAL"],
            "total_effort_hours": sum(a["estimated_effort_hours"] for a in remediation_groups["CRITICAL"])
        })

    # Phase 2: High priority issues
    if remediation_groups["HIGH"]:
        action_plan.append({
            "phase": 2,
            "title": "⚠️ High Priority Issues - Fix Before Merge",
            "description": "These issues should be resolved before merging to main branch",
            "actions": remediation_groups["HIGH"],
            "total_effort_hours": sum(a["estimated_effort_hours"] for a in remediation_groups["HIGH"])
        })

    # Phase 3: Medium priority issues
    if remediation_groups["MEDIUM"]:
        action_plan.append({
            "phase": 3,
            "title": "📋 Medium Priority Issues - Plan to Address",
            "description": "These issues should be addressed in the near future",
            "actions": remediation_groups["MEDIUM"],
            "total_effort_hours": sum(a["estimated_effort_hours"] for a in remediation_groups["MEDIUM"])
        })

    # Phase 4: Low priority issues
    if remediation_groups["LOW"]:
        action_plan.append({
            "phase": 4,
            "title": "💡 Low Priority Issues - Nice to Have",
            "description": "These are recommendations for code quality improvements",
            "actions": remediation_groups["LOW"],
            "total_effort_hours": sum(a["estimated_effort_hours"] for a in remediation_groups["LOW"])
        })

    # Calculate total effort
    total_effort = sum(phase["total_effort_hours"] for phase in action_plan)

    return {
        "action_plan": action_plan,
        "total_phases": len(action_plan),
        "total_effort_hours": total_effort,
        "total_effort_days": round(total_effort / 8, 1),  # Assuming 8-hour work days
        "immediate_actions_required": len(remediation_groups["CRITICAL"]) > 0
    }


@tool("calculate_effort_estimation")
def calculate_effort_estimation_tool(remediation_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate detailed effort estimation for remediation

    Args:
        remediation_plan: The remediation plan with actions

    Returns:
        Detailed effort breakdown with timeline
    """
    logger.info("Calculating effort estimation")

    effort_breakdown = {
        "by_severity": {},
        "by_technology": {},
        "by_phase": {},
        "timeline": {}
    }

    # Extract action plan
    action_plan = remediation_plan.get("action_plan", [])

    for phase in action_plan:
        phase_num = phase["phase"]
        phase_title = phase["title"]
        phase_effort = phase["total_effort_hours"]

        effort_breakdown["by_phase"][f"Phase {phase_num}"] = {
            "title": phase_title,
            "hours": phase_effort,
            "days": round(phase_effort / 8, 1)
        }

        # Break down by technology and severity
        for action in phase["actions"]:
            technology = action["technology"]
            severity = _get_severity_from_phase(phase_num)

            # By technology
            if technology not in effort_breakdown["by_technology"]:
                effort_breakdown["by_technology"][technology] = 0
            effort_breakdown["by_technology"][technology] += action["estimated_effort_hours"]

            # By severity
            if severity not in effort_breakdown["by_severity"]:
                effort_breakdown["by_severity"][severity] = 0
            effort_breakdown["by_severity"][severity] += action["estimated_effort_hours"]

    # Create timeline
    total_hours = remediation_plan.get("total_effort_hours", 0)
    if total_hours > 0:
        if total_hours <= 8:
            timeline = "Can be completed in 1 day"
        elif total_hours <= 40:
            timeline = f"Can be completed in {round(total_hours / 8, 1)} days (1 week)"
        else:
            weeks = round(total_hours / 40, 1)
            timeline = f"Requires approximately {weeks} weeks to complete"
    else:
        timeline = "No remediation required"

    effort_breakdown["timeline"] = {
        "total_hours": total_hours,
        "total_days": round(total_hours / 8, 1),
        "estimated_completion": timeline,
        "recommendation": _get_timeline_recommendation(total_hours)
    }

    return effort_breakdown


@tool("format_executive_report")
def format_executive_report_tool(
        summary: Dict[str, Any],
        remediation_plan: Dict[str, Any],
        effort_estimation: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format all validation results into an executive report

    Args:
        summary: Validation summary
        remediation_plan: Remediation plan
        effort_estimation: Effort estimation

    Returns:
        Formatted executive report
    """
    logger.info("Formatting executive report")

    # Extract key metrics
    production_ready = summary.get("production_ready", False)
    critical_issues = summary.get("critical_issues_count", 0)
    total_issues = summary.get("statistics", {}).get("failed_checkpoints", 0)
    pass_rate = summary.get("statistics", {}).get("pass_rate", 0)

    # Create executive summary
    if production_ready:
        executive_summary = (
            f"✅ **PRODUCTION READY** - The pull request has passed all critical validation checkpoints. "
            f"While there are {total_issues} non-critical issues identified, none prevent deployment. "
            f"The overall compliance rate is {pass_rate}%."
        )
        recommendation = "APPROVE for production deployment with follow-up tasks for non-critical issues."
    else:
        executive_summary = (
            f"❌ **NOT PRODUCTION READY** - The pull request has {critical_issues} critical issues "
            f"that must be resolved before deployment. Total issues found: {total_issues}. "
            f"Current compliance rate: {pass_rate}%."
        )
        recommendation = "BLOCK deployment until all critical issues are resolved."

    # Technology summary
    tech_summary = []
    for tech, stats in summary.get("technology_breakdown", {}).items():
        status = "✅" if stats["critical_issues"] == 0 else "❌"
        tech_summary.append({
            "technology": tech,
            "status": status,
            "issues": f"{stats['failed']}/{stats['total']} checkpoints failed",
            "critical": stats["critical_issues"]
        })

    # Key risks
    key_risks = []
    if critical_issues > 0:
        key_risks.append(f"Critical security or operational issues detected ({critical_issues} issues)")

    high_issues = summary.get("severity_breakdown", {}).get("HIGH", {}).get("failed", 0)
    if high_issues > 5:
        key_risks.append(f"High number of HIGH severity issues ({high_issues}) indicating technical debt")

    if pass_rate < 70:
        key_risks.append(f"Low compliance rate ({pass_rate}%) suggests rushed development")

    # Format the complete report
    report = {
        "report_metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "report_version": "1.0",
            "validation_framework": "PR Validation System v1.0"
        },
        "executive_summary": {
            "headline": "PRODUCTION READY" if production_ready else "NOT PRODUCTION READY",
            "summary": executive_summary,
            "recommendation": recommendation,
            "key_metrics": {
                "production_ready": production_ready,
                "critical_issues": critical_issues,
                "total_issues": total_issues,
                "compliance_rate": f"{pass_rate}%",
                "estimated_fix_time": effort_estimation.get("timeline", {}).get("estimated_completion", "Unknown")
            }
        },
        "technology_summary": tech_summary,
        "risk_assessment": {
            "risk_level": _calculate_risk_level(critical_issues, total_issues, pass_rate),
            "key_risks": key_risks,
            "mitigation_required": len(key_risks) > 0
        },
        "remediation_summary": {
            "immediate_actions": remediation_plan.get("immediate_actions_required", False),
            "total_effort_days": effort_estimation.get("timeline", {}).get("total_days", 0),
            "phases": len(remediation_plan.get("action_plan", [])),
            "priority_breakdown": {
                severity: hours
                for severity, hours in effort_estimation.get("by_severity", {}).items()
            }
        },
        "next_steps": _generate_next_steps(production_ready, critical_issues, total_issues),
        "detailed_results": {
            "summary": summary,
            "remediation_plan": remediation_plan,
            "effort_estimation": effort_estimation
        }
    }

    return report


# Helper functions

def _estimate_effort(severity: str, violation_count: int) -> float:
    """Estimate effort in hours based on severity and number of violations"""
    base_hours = {
        "CRITICAL": 2.0,
        "HIGH": 1.5,
        "MEDIUM": 1.0,
        "LOW": 0.5
    }

    base = base_hours.get(severity, 1.0)
    # Add additional time for multiple violations
    multiplier = 1 + (0.2 * (violation_count - 1)) if violation_count > 1 else 1

    return round(base * multiplier, 1)


def _get_severity_from_phase(phase_num: int) -> str:
    """Map phase number to severity"""
    phase_severity_map = {
        1: "CRITICAL",
        2: "HIGH",
        3: "MEDIUM",
        4: "LOW"
    }
    return phase_severity_map.get(phase_num, "MEDIUM")


def _get_timeline_recommendation(total_hours: float) -> str:
    """Get recommendation based on total effort"""
    if total_hours == 0:
        return "No action required - ready for deployment"
    elif total_hours <= 4:
        return "Quick fixes - can be addressed immediately"
    elif total_hours <= 8:
        return "Address within current sprint"
    elif total_hours <= 40:
        return "Plan for dedicated sprint time"
    else:
        return "Consider breaking into multiple PRs or dedicating a full sprint"


def _calculate_risk_level(critical_issues: int, total_issues: int, pass_rate: float) -> str:
    """Calculate overall risk level"""
    if critical_issues > 0:
        return "HIGH"
    elif total_issues > 10 or pass_rate < 70:
        return "MEDIUM"
    elif total_issues > 5 or pass_rate < 85:
        return "LOW"
    else:
        return "MINIMAL"


def _generate_next_steps(production_ready: bool, critical_issues: int, total_issues: int) -> List[str]:
    """Generate recommended next steps"""
    steps = []

    if not production_ready:
        steps.append("1. Address all CRITICAL issues immediately")
        steps.append("2. Re-run validation after fixes")
        steps.append("3. Get approval from tech lead")
    else:
        if total_issues > 0:
            steps.append("1. Create follow-up tasks for non-critical issues")
            steps.append("2. Plan remediation in next sprint")
        steps.append("3. Deploy to production with monitoring")
        steps.append("4. Document any known issues")

    return steps
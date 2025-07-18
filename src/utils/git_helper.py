# Git Helper Utilities

import subprocess
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("utils.git_helper")


class GitHelper:
    """Helper class for Git operations"""

    def __init__(self, repo_path: str = "."):
        """
        Initialize Git helper

        Args:
            repo_path: Path to git repository
        """
        self.repo_path = Path(repo_path).resolve()
        self.logger = logger

    def run_git_command(self, command: List[str]) -> tuple[str, str, int]:
        """
        Run a git command and return output

        Args:
            command: Git command as list of arguments

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        try:
            cmd = ["git"] + command
            self.logger.debug(f"Running git command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            return result.stdout, result.stderr, result.returncode

        except subprocess.TimeoutExpired:
            self.logger.error(f"Git command timed out: {' '.join(command)}")
            return "", "Command timed out", 1
        except Exception as e:
            self.logger.error(f"Error running git command: {str(e)}")
            return "", str(e), 1

    def get_modified_files(self, base_branch: str = "main", target_branch: Optional[str] = None) -> List[
        Dict[str, Any]]:
        """
        Get list of modified files between branches

        Args:
            base_branch: Base branch to compare against
            target_branch: Target branch (current branch if None)

        Returns:
            List of modified files with details
        """
        files = []

        # Get current branch if target not specified
        if not target_branch:
            stdout, _, _ = self.run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
            target_branch = stdout.strip()

        # Get diff between branches
        stdout, stderr, code = self.run_git_command([
            "diff",
            f"{base_branch}...{target_branch}",
            "--name-status"
        ])

        if code != 0:
            self.logger.error(f"Failed to get diff: {stderr}")
            return files

        # Parse diff output
        for line in stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split('\t')
            if len(parts) >= 2:
                status = parts[0]
                file_path = parts[1]

                # Map git status to change type
                change_type_map = {
                    'A': 'add',
                    'M': 'edit',
                    'D': 'delete',
                    'R': 'rename',
                    'C': 'copy'
                }

                change_type = change_type_map.get(status[0], 'edit')

                files.append({
                    "path": file_path,
                    "change_type": change_type,
                    "status": status
                })

        self.logger.info(f"Found {len(files)} modified files between {base_branch} and {target_branch}")
        return files

    def get_file_content(self, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """
        Get content of a file at specific ref

        Args:
            file_path: Path to file
            ref: Git ref (commit, branch, tag)

        Returns:
            File content or None if error
        """
        stdout, stderr, code = self.run_git_command([
            "show",
            f"{ref}:{file_path}"
        ])

        if code != 0:
            self.logger.error(f"Failed to get file content for {file_path} at {ref}: {stderr}")
            return None

        return stdout

    def get_commit_info(self, ref: str = "HEAD") -> Dict[str, Any]:
        """
        Get commit information

        Args:
            ref: Git ref

        Returns:
            Commit information dictionary
        """
        # Get commit hash
        stdout, _, _ = self.run_git_command(["rev-parse", ref])
        commit_hash = stdout.strip()

        # Get commit details
        stdout, _, _ = self.run_git_command([
            "show",
            "--no-patch",
            "--format=%an|%ae|%at|%s",
            ref
        ])

        parts = stdout.strip().split('|')
        if len(parts) >= 4:
            return {
                "hash": commit_hash,
                "author_name": parts[0],
                "author_email": parts[1],
                "timestamp": parts[2],
                "message": parts[3]
            }

        return {"hash": commit_hash}

    def get_branch_info(self) -> Dict[str, str]:
        """
        Get current branch information

        Returns:
            Branch information dictionary
        """
        # Get current branch
        stdout, _, _ = self.run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
        current_branch = stdout.strip()

        # Get remote tracking branch
        stdout, _, _ = self.run_git_command([
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{u}"
        ])
        tracking_branch = stdout.strip() if stdout else None

        return {
            "current": current_branch,
            "tracking": tracking_branch
        }

    def get_file_history(self, file_path: str, max_commits: int = 10) -> List[Dict[str, Any]]:
        """
        Get commit history for a specific file

        Args:
            file_path: Path to file
            max_commits: Maximum number of commits to return

        Returns:
            List of commit information
        """
        stdout, stderr, code = self.run_git_command([
            "log",
            f"--max-count={max_commits}",
            "--format=%H|%an|%ae|%at|%s",
            "--",
            file_path
        ])

        if code != 0:
            self.logger.error(f"Failed to get file history: {stderr}")
            return []

        commits = []
        for line in stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split('|')
            if len(parts) >= 5:
                commits.append({
                    "hash": parts[0],
                    "author_name": parts[1],
                    "author_email": parts[2],
                    "timestamp": parts[3],
                    "message": parts[4]
                })

        return commits

    def check_file_exists(self, file_path: str, ref: str = "HEAD") -> bool:
        """
        Check if file exists at specific ref

        Args:
            file_path: Path to file
            ref: Git ref

        Returns:
            True if file exists
        """
        _, _, code = self.run_git_command([
            "cat-file",
            "-e",
            f"{ref}:{file_path}"
        ])

        return code == 0

    def get_merge_base(self, branch1: str, branch2: str) -> Optional[str]:
        """
        Get merge base commit between two branches

        Args:
            branch1: First branch
            branch2: Second branch

        Returns:
            Merge base commit hash
        """
        stdout, stderr, code = self.run_git_command([
            "merge-base",
            branch1,
            branch2
        ])

        if code != 0:
            self.logger.error(f"Failed to get merge base: {stderr}")
            return None

        return stdout.strip()


# Singleton instance
_git_helper: Optional[GitHelper] = None


def get_git_helper(repo_path: str = ".") -> GitHelper:
    """
    Get or create GitHelper instance

    Args:
        repo_path: Repository path

    Returns:
        GitHelper instance
    """
    global _git_helper
    if _git_helper is None or _git_helper.repo_path != Path(repo_path).resolve():
        _git_helper = GitHelper(repo_path)
    return _git_helper
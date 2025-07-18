# Azure DevOps Client Utilities

import aiohttp
import asyncio
from typing import Dict, Any, List, Optional
import base64
import json
from datetime import datetime

from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("utils.azure_devops")


class AzureDevOpsClient:
    """Client for interacting with Azure DevOps API"""

    def __init__(self, organization_url: str, project: str, repository: str, pat: str):
        """
        Initialize Azure DevOps client

        Args:
            organization_url: Azure DevOps organization URL
            project: Project name
            repository: Repository name
            pat: Personal Access Token
        """
        self.organization_url = organization_url.rstrip('/')
        self.project = project
        self.repository = repository
        self.pat = pat

        # Setup authentication
        self.headers = {
            'Authorization': f'Basic {base64.b64encode(f":{pat}".encode()).decode()}',
            'Content-Type': 'application/json'
        }

        # Extract organization name from URL
        self.organization = self.organization_url.split('/')[-1]

        # API base URL
        self.api_base = f"https://dev.azure.com/{self.organization}/{self.project}/_apis"

        logger.info(f"Initialized Azure DevOps client for {self.organization}/{self.project}")

    async def get_file_content(self, file_path: str, branch: str) -> str:
        """
        Get file content from repository

        Args:
            file_path: Path to file in repository
            branch: Branch name

        Returns:
            File content as string
        """
        try:
            # Remove leading slash if present
            file_path = file_path.lstrip('/')

            # Construct API URL
            url = f"{self.api_base}/git/repositories/{self.repository}/items"
            params = {
                'path': file_path,
                'versionDescriptor.version': branch.replace('refs/heads/', ''),
                'api-version': '7.0'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Successfully fetched content for {file_path}")
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to fetch {file_path}: {response.status} - {error_text}")
                        return ""

        except Exception as e:
            logger.error(f"Error fetching file content for {file_path}: {str(e)}")
            return ""

    async def get_pr_details(self, pr_id: str) -> Dict[str, Any]:
        """
        Get pull request details

        Args:
            pr_id: Pull request ID

        Returns:
            PR details dictionary
        """
        try:
            url = f"{self.api_base}/git/repositories/{self.repository}/pullrequests/{pr_id}"
            params = {'api-version': '7.0'}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Successfully fetched PR details for {pr_id}")
                        return data
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to fetch PR {pr_id}: {response.status} - {error_text}")
                        return {}

        except Exception as e:
            logger.error(f"Error fetching PR details for {pr_id}: {str(e)}")
            return {}

    async def get_pr_files(self, pr_id: str) -> List[Dict[str, Any]]:
        """
        Get list of files modified in a pull request

        Args:
            pr_id: Pull request ID

        Returns:
            List of modified files
        """
        try:
            # Get PR iterations
            url = f"{self.api_base}/git/repositories/{self.repository}/pullrequests/{pr_id}/iterations"
            params = {'api-version': '7.0'}

            async with aiohttp.ClientSession() as session:
                # Get iterations
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get PR iterations: {response.status}")
                        return []

                    iterations = await response.json()
                    if not iterations.get('value'):
                        return []

                    # Get latest iteration
                    latest_iteration = iterations['value'][-1]['id']

                # Get changes from latest iteration
                changes_url = f"{url}/{latest_iteration}/changes"
                async with session.get(changes_url, headers=self.headers, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get PR changes: {response.status}")
                        return []

                    changes = await response.json()

                    # Format file list
                    files = []
                    for change in changes.get('changeEntries', []):
                        files.append({
                            'path': change.get('item', {}).get('path', ''),
                            'changeType': change.get('changeType', 'edit').lower(),
                            'item': change.get('item', {})
                        })

                    logger.info(f"Found {len(files)} modified files in PR {pr_id}")
                    return files

        except Exception as e:
            logger.error(f"Error fetching PR files for {pr_id}: {str(e)}")
            return []

    async def post_pr_comment(self, pr_id: str, comment: str) -> bool:
        """
        Post a comment on a pull request

        Args:
            pr_id: Pull request ID
            comment: Comment text (markdown supported)

        Returns:
            Success status
        """
        try:
            url = f"{self.api_base}/git/repositories/{self.repository}/pullrequests/{pr_id}/threads"
            params = {'api-version': '7.0'}

            # Create comment thread
            data = {
                "comments": [
                    {
                        "parentCommentId": 0,
                        "content": comment,
                        "commentType": 1  # 1 = text
                    }
                ],
                "status": 1  # 1 = active
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, params=params, json=data) as response:
                    if response.status in [200, 201]:
                        logger.info(f"Successfully posted comment to PR {pr_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to post comment: {response.status} - {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Error posting comment to PR {pr_id}: {str(e)}")
            return False

    async def update_pr_status(self, pr_id: str, status: str, description: str, context: str) -> bool:
        """
        Update pull request status

        Args:
            pr_id: Pull request ID
            status: Status (succeeded, failed, pending)
            description: Status description
            context: Status context name

        Returns:
            Success status
        """
        try:
            # First get PR details to get the last commit ID
            pr_details = await self.get_pr_details(pr_id)
            if not pr_details:
                return False

            commit_id = pr_details.get('lastMergeSourceCommit', {}).get('commitId')
            if not commit_id:
                logger.error("Could not get commit ID from PR")
                return False

            # Update status
            url = f"{self.api_base}/git/repositories/{self.repository}/commits/{commit_id}/statuses"
            params = {'api-version': '7.0'}

            data = {
                "state": status,
                "description": description[:140],  # Max 140 characters
                "targetUrl": f"{self.organization_url}/{self.project}/_git/{self.repository}/pullrequest/{pr_id}",
                "context": {
                    "name": context,
                    "genre": "continuous-integration"
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, params=params, json=data) as response:
                    if response.status in [200, 201]:
                        logger.info(f"Successfully updated PR {pr_id} status to {status}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to update status: {response.status} - {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Error updating PR {pr_id} status: {str(e)}")
            return False

    async def get_repository_info(self) -> Dict[str, Any]:
        """
        Get repository information

        Returns:
            Repository information dictionary
        """
        try:
            url = f"{self.api_base}/git/repositories/{self.repository}"
            params = {'api-version': '7.0'}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Successfully fetched repository info for {self.repository}")
                        return data
                    else:
                        logger.error(f"Failed to fetch repository info: {response.status}")
                        return {}

        except Exception as e:
            logger.error(f"Error fetching repository info: {str(e)}")
            return {}

    async def create_pr_work_item(self, pr_id: str, work_item_type: str, title: str, description: str) -> Optional[int]:
        """
        Create a work item linked to a pull request

        Args:
            pr_id: Pull request ID
            work_item_type: Type of work item (Bug, Task, etc.)
            title: Work item title
            description: Work item description

        Returns:
            Work item ID if created successfully
        """
        try:
            # Create work item
            url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/wit/workitems/${work_item_type}"
            params = {'api-version': '7.0'}

            # Work item patch document
            patch_document = [
                {
                    "op": "add",
                    "path": "/fields/System.Title",
                    "value": title
                },
                {
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": description
                },
                {
                    "op": "add",
                    "path": "/fields/System.Tags",
                    "value": "PR-Validation"
                }
            ]

            headers = self.headers.copy()
            headers['Content-Type'] = 'application/json-patch+json'

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, params=params, json=patch_document) as response:
                    if response.status in [200, 201]:
                        work_item = await response.json()
                        work_item_id = work_item.get('id')

                        # Link work item to PR
                        if work_item_id:
                            await self._link_work_item_to_pr(pr_id, work_item_id)

                        logger.info(f"Successfully created work item {work_item_id} for PR {pr_id}")
                        return work_item_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create work item: {response.status} - {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Error creating work item for PR {pr_id}: {str(e)}")
            return None

    async def _link_work_item_to_pr(self, pr_id: str, work_item_id: int) -> bool:
        """
        Link a work item to a pull request

        Args:
            pr_id: Pull request ID
            work_item_id: Work item ID

        Returns:
            Success status
        """
        try:
            url = f"{self.api_base}/git/repositories/{self.repository}/pullrequests/{pr_id}/workitems"
            params = {'api-version': '7.0'}

            data = [{"id": str(work_item_id)}]

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, params=params, json=data) as response:
                    return response.status in [200, 201]

        except Exception as e:
            logger.error(f"Error linking work item {work_item_id} to PR {pr_id}: {str(e)}")
            return False
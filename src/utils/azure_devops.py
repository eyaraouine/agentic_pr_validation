# src/utils/azure_devops.py - Version améliorée

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

        # Setup authentication - fix the base64 encoding
        auth_string = f":{pat}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode('ascii')
        self.headers = {
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # Extract organization name from URL
        if "dev.azure.com" in self.organization_url:
            # New URL format: https://dev.azure.com/organization
            parts = self.organization_url.split('/')
            self.organization = parts[-1] if parts else "unknown"
        else:
            # Old URL format: https://organization.visualstudio.com
            self.organization = self.organization_url.split('//')[1].split('.')[0]

        # API base URL
        self.api_base = f"https://dev.azure.com/{self.organization}/{self.project}/_apis"

        logger.info(f"Initialized Azure DevOps client for {self.organization}/{self.project}")

    async def test_connection(self) -> bool:
        """
        Test if the connection and authentication work

        Returns:
            True if connection successful
        """
        try:
            url = f"{self.api_base}/git/repositories/{self.repository}"
            params = {'api-version': '7.0'}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        logger.info("Azure DevOps connection test successful")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Connection test failed: {response.status} - {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Connection test error: {str(e)}")
            return False

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
            # Remove leading slash and clean path
            file_path = file_path.lstrip('/').replace('//', '/')

            # Clean branch name (remove refs/heads/ if present)
            branch_name = branch.replace('refs/heads/', '')

            # Try different API endpoints
            # Method 1: Items API
            url = f"{self.api_base}/git/repositories/{self.repository}/items"
            params = {
                'path': f"/{file_path}",  # Add leading slash for API
                'versionDescriptor.version': branch_name,
                'versionDescriptor.versionType': 'branch',
                '$format': 'text',  # Get raw content
                'api-version': '7.0'
            }

            logger.debug(f"Fetching file: {file_path} from branch: {branch_name}")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Successfully fetched {len(content)} bytes for {file_path}")
                        return content
                    elif response.status == 404:
                        logger.warning(f"File not found: {file_path} in branch {branch_name}")
                        # Try alternate method
                        return await self._get_file_content_alternate(file_path, branch_name)
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to fetch {file_path}: {response.status} - {error_text}")

                        # If authentication error, provide helpful message
                        if response.status == 401:
                            logger.error(
                                "Authentication failed. Please check your PAT token has Code (read) permission")

                        return ""

        except Exception as e:
            logger.error(f"Error fetching file content for {file_path}: {str(e)}")
            return ""

    async def _get_file_content_alternate(self, file_path: str, branch: str) -> str:
        """
        Alternative method to get file content using commits API
        """
        try:
            # Get latest commit on branch
            url = f"{self.api_base}/git/repositories/{self.repository}/commits"
            params = {
                'searchCriteria.itemVersion.version': branch,
                'searchCriteria.itemVersion.versionType': 'branch',
                '$top': 1,
                'api-version': '7.0'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status != 200:
                        return ""

                    data = await response.json()
                    if not data.get('value'):
                        return ""

                    commit_id = data['value'][0]['commitId']

                    # Get file from commit
                    file_url = f"{self.api_base}/git/repositories/{self.repository}/items"
                    file_params = {
                        'path': f"/{file_path}",
                        'versionDescriptor.version': commit_id,
                        'versionDescriptor.versionType': 'commit',
                        '$format': 'text',
                        'api-version': '7.0'
                    }

                    async with session.get(file_url, headers=self.headers, params=file_params) as file_response:
                        if file_response.status == 200:
                            content = await file_response.text()
                            logger.info(f"Successfully fetched {file_path} using alternate method")
                            return content

            return ""

        except Exception as e:
            logger.error(f"Alternate fetch method failed: {str(e)}")
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
            # Handle both numeric and string PR IDs
            pr_id_numeric = pr_id.split('-')[-1] if '-' in pr_id else pr_id

            url = f"{self.api_base}/git/repositories/{self.repository}/pullrequests/{pr_id_numeric}"
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
            # Handle both numeric and string PR IDs
            pr_id_numeric = pr_id.split('-')[-1] if '-' in pr_id else pr_id

            # Get PR iterations
            url = f"{self.api_base}/git/repositories/{self.repository}/pullrequests/{pr_id_numeric}/iterations"
            params = {'api-version': '7.0'}

            async with aiohttp.ClientSession() as session:
                # Get iterations
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get PR iterations: {response.status} - {error_text}")
                        return []

                    iterations = await response.json()
                    if not iterations.get('value'):
                        logger.warning(f"No iterations found for PR {pr_id}")
                        return []

                    # Get latest iteration
                    latest_iteration = iterations['value'][-1]['id']

                # Get changes from latest iteration
                changes_url = f"{url}/{latest_iteration}/changes"
                async with session.get(changes_url, headers=self.headers, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to get PR changes: {response.status} - {error_text}")
                        return []

                    changes = await response.json()

                    # Format file list
                    files = []
                    for change in changes.get('changeEntries', []):
                        change_type_map = {
                            1: 'add',  # Add
                            2: 'edit',  # Edit
                            4: 'rename',  # Rename
                            8: 'delete',  # Delete
                            16: 'undelete',  # Undelete
                            32: 'branch',  # Branch
                            64: 'merge',  # Merge
                            128: 'lock',  # Lock
                            256: 'property'  # Property
                        }

                        change_type_value = change.get('changeType', 2)
                        change_type = change_type_map.get(change_type_value, 'edit')

                        files.append({
                            'path': change.get('item', {}).get('path', ''),
                            'changeType': change_type,
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
            # Handle both numeric and string PR IDs
            pr_id_numeric = pr_id.split('-')[-1] if '-' in pr_id else pr_id

            url = f"{self.api_base}/git/repositories/{self.repository}/pullrequests/{pr_id_numeric}/threads"
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
            # Handle both numeric and string PR IDs
            pr_id_numeric = pr_id.split('-')[-1] if '-' in pr_id else pr_id

            # First get PR details to get the last commit ID
            pr_details = await self.get_pr_details(pr_id)
            if not pr_details:
                logger.error("Could not get PR details for status update")
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
                "targetUrl": f"{self.organization_url}/{self.project}/_git/{self.repository}/pullrequest/{pr_id_numeric}",
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
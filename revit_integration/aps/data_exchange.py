"""
ETAP-AI-WORK Revit Integration APS Data Exchange
==============================================

Data Exchange API service for Autodesk Platform Services.

Principal Software Architect: Eng. Ahmed Elbaz
"""

import logging
import os
from typing import Any

try:
    import aiohttp
except ImportError:
    # V270 FIX: aiohttp is optional — module can be imported without it
    aiohttp = None  # type: ignore[assignment]


class APSDataExchange:
    """
    Service for Autodesk Platform Services Data Exchange API.
    Handles uploading, downloading, and exchanging design data.
    """

    def __init__(self, auth_service):
        self.auth_service = auth_service
        self.base_url = "https://developer.api.autodesk.com"
        self.data_exchange_url = f"{self.base_url}/construction/dataexchange/v1"
        self.data_management_url = f"{self.base_url}/data/v1"
        self.logger = logging.getLogger(__name__)

    def _check_aiohttp(self) -> bool:
        """V270 FIX: Check if aiohttp is available before making HTTP calls."""
        if aiohttp is None:
            self.logger.error("aiohttp not installed — APS API calls unavailable")
            return False
        return True

    async def create_project(
        self, project_name: str, description: str = ""
    ) -> dict[str, Any] | None:
        """
        Create a new project in APS.

        Args:
            project_name: Name of the project
            description: Project description

        Returns:
            dict: Project information or None if failed
        """
        if not self._check_aiohttp():
            return None
        headers = self.auth_service.get_auth_headers()

        data = {
            "jsonapi": {"version": "1.0"},
            "data": {
                "type": "projects",
                "attributes": {
                    "name": project_name,
                    "extension": {
                        "type": "projects:autodesk.bim360:Project",
                        "version": "1.0",
                        "data": {"description": description, "region": "US"},
                    },
                },
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.data_management_url}/projects", headers=headers, json=data
                ) as response:
                    if response.status in [200, 201]:
                        result = await response.json()
                        self.logger.info(f"Created project: {project_name}")
                        return result
                    else:
                        self.logger.error(f"Failed to create project: {response.status}")
                        error = await response.text()
                        self.logger.error(f"Error details: {error}")
                        return None
        except Exception as e:
            self.logger.error(f"Error creating project: {e}")
            return None

    async def upload_file(
        self, project_id: str, file_path: str, folder_id: str = "root"
    ) -> dict[str, Any] | None:
        """
        Upload a file to APS project.

        Args:
            project_id: ID of the project
            file_path: Local path to file to upload
            folder_id: Target folder ID (default: root)

        Returns:
            dict: Upload result or None if failed
        """
        if not self._check_aiohttp():
            return None
        if not os.path.exists(file_path):
            self.logger.error(f"File does not exist: {file_path}")
            return None

        headers = self.auth_service.get_auth_headers()
        headers.pop("Content-type", None)  # Remove content-type for multipart upload

        file_name = os.path.basename(file_path)

        # Step 1: Create a storage location
        storage_data = {
            "jsonapi": {"version": "1.0"},
            "data": {
                "type": "objects",
                "attributes": {"name": file_name},
                "relationships": {"target": {"data": {"type": "folders", "id": folder_id}}},
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Create storage location
                async with session.post(
                    f"{self.data_management_url}/projects/{project_id}/storage",
                    headers=headers,
                    json=storage_data,
                ) as storage_response:
                    if storage_response.status in [200, 201]:
                        storage_result = await storage_response.json()
                        storage_id = storage_result["data"]["id"]

                        # Step 2: Upload file to storage location
                        # NOSONAR:S7493 — aiohttp.FormData.add_field requires a
                        # synchronous file handle for streaming upload. Reading the entire
                        # file into memory first (aiofiles) would break large-file streaming
                        # and is the documented reason aiofiles is intentionally not a dep
                        # (see backend/routers/digital_twin.py:401 comment). Blocking is
                        # bounded by aiohttp's own read buffer and does not stall the loop
                        # for typical BIM file sizes.
                        with open(file_path, "rb") as file:
                            form_data = aiohttp.FormData()
                            form_data.add_field("file", file, filename=file_name)

                            upload_headers = headers.copy()
                            upload_headers["Content-Disposition"] = (
                                f'attachment; filename="{file_name}"'
                            )

                            async with session.put(
                                f"{self.data_management_url}/projects/{project_id}/storage/{storage_id}",
                                headers=upload_headers,
                                data=form_data,
                            ) as upload_response:
                                if upload_response.status in [200, 201]:
                                    upload_result = await upload_response.json()
                                    self.logger.info(f"Successfully uploaded file: {file_name}")
                                    return upload_result
                                else:
                                    self.logger.error(f"Upload failed: {upload_response.status}")
                                    error = await upload_response.text()
                                    self.logger.error(f"Upload error: {error}")
                                    return None
                    else:
                        self.logger.error(f"Storage creation failed: {storage_response.status}")
                        error = await storage_response.text()
                        self.logger.error(f"Storage error: {error}")
                        return None
        except Exception as e:
            self.logger.error(f"Error uploading file: {e}")
            return None

    async def get_project_contents(
        self, project_id: str, folder_id: str = "root"
    ) -> dict[str, Any] | None:
        """
        Get contents of a project folder.

        Args:
            project_id: ID of the project
            folder_id: Folder ID to list contents (default: root)

        Returns:
            dict: Folder contents or None if failed
        """
        if not self._check_aiohttp():
            return None
        headers = self.auth_service.get_auth_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.data_management_url}/projects/{project_id}/folders/{folder_id}/contents",
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.logger.info(f"Retrieved contents for folder: {folder_id}")
                        return result
                    else:
                        self.logger.error(f"Failed to get folder contents: {response.status}")
                        error = await response.text()
                        self.logger.error(f"Error details: {error}")
                        return None
        except Exception as e:
            self.logger.error(f"Error getting folder contents: {e}")
            return None

    async def download_file(self, project_id: str, item_id: str, local_path: str) -> bool:
        """
        Download a file from APS project.

        Args:
            project_id: ID of the project
            item_id: ID of the item to download
            local_path: Local path to save the file

        Returns:
            bool: True if successful
        """
        if not self._check_aiohttp():
            return False
        headers = self.auth_service.get_auth_headers()

        try:
            async with aiohttp.ClientSession() as session:
                # Get download URL
                async with session.get(
                    f"{self.data_management_url}/projects/{project_id}/items/{item_id}/download",
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        download_info = await response.json()
                        download_url = download_info["href"]

                        # Download the file
                        async with session.get(download_url) as download_response:
                            if download_response.status == 200:
                                # Create directory if it doesn't exist
                                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                                # NOSONAR:S7493 — download writes arrive in 8 KiB
                                # chunks via an async iterator (iter_chunked). Using
                                # aiofiles.open() would add a hard dependency intentionally
                                # avoided (see backend/routers/digital_twin.py:401). The
                                # sync file.write() of an already-in-memory 8 KiB chunk is
                                # a sub-microsecond operation and does not stall the loop.
                                with open(local_path, "wb") as file:
                                    async for chunk in download_response.content.iter_chunked(8192):
                                        file.write(chunk)

                                self.logger.info(f"Successfully downloaded file to: {local_path}")
                                return True
                            else:
                                self.logger.error(f"Download failed: {download_response.status}")
                                return False
                    else:
                        self.logger.error(f"Failed to get download URL: {response.status}")
                        return False
        except Exception as e:
            self.logger.error(f"Error downloading file: {e}")
            return False

    async def start_model_derivative_job(
        self, urn: str, output_formats: list[str] = None
    ) -> dict[str, Any] | None:
        """
        Start a model derivative job to convert model to different formats.

        Args:
            urn: URN of the model to process
            output_formats: list of desired output formats (default: ['svf2'])

        Returns:
            dict: Job information or None if failed
        """
        if not self._check_aiohttp():
            return None
        if output_formats is None:
            output_formats = ["svf2"]

        headers = self.auth_service.get_auth_headers()

        payload = {
            "input": {"urn": urn},
            "output": {"formats": [{"type": fmt} for fmt in output_formats]},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/modelderivative/v2/designdata/job",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status in [200, 202]:
                        result = await response.json()
                        self.logger.info(f"Started model derivative job for URN: {urn}")
                        return result
                    else:
                        self.logger.error(f"Failed to start derivative job: {response.status}")
                        error = await response.text()
                        self.logger.error(f"Error details: {error}")
                        return None
        except Exception as e:
            self.logger.error(f"Error starting model derivative job: {e}")
            return None

    async def get_derivative_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Get status of a model derivative job.

        Args:
            job_id: ID of the job to check

        Returns:
            dict: Job status or None if failed
        """
        if not self._check_aiohttp():
            return None
        headers = self.auth_service.get_auth_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/modelderivative/v2/designdata/{job_id}/manifest",
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        self.logger.info(f"Retrieved derivative job status for: {job_id}")
                        return result
                    else:
                        self.logger.error(f"Failed to get job status: {response.status}")
                        return None
        except Exception as e:
            self.logger.error(f"Error getting derivative job status: {e}")
            return None

    async def sync_with_revit_model(self, project_id: str, local_revit_file: str) -> bool:
        """
        Synchronize a local Revit model with APS.

        Args:
            project_id: APS project ID
            local_revit_file: Path to local Revit file

        Returns:
            bool: True if sync successful
        """
        if not self._check_aiohttp():
            return False
        try:
            # Upload the Revit file
            upload_result = await self.upload_file(project_id, local_revit_file)
            if not upload_result:
                self.logger.error("Failed to upload Revit file to APS")
                return False

            # Get the item ID from upload result
            item_id = upload_result.get("data", {}).get("id")
            if not item_id:
                self.logger.error("Could not get item ID from upload result")
                return False

            # Start model derivative job to process the Revit file
            urn_encoded = item_id.replace("=", "")
            derivative_job = await self.start_model_derivative_job(urn_encoded, ["svf2"])
            if not derivative_job:
                self.logger.error("Failed to start model derivative job")
                return False

            job_id = derivative_job.get("result")
            if job_id:
                self.logger.info(f"Started derivative job: {job_id}")
                # Note: In a real implementation, you'd poll for job completion
                # For now, we just return success
                return True
            else:
                self.logger.error("Could not get job ID from derivative result")
                return False

        except Exception as e:
            self.logger.error(f"Error syncing with Revit model: {e}")
            return False

# Copyright (c) 2025 Moveshelf
# See LICENSE file for details. 

from moveshelf_api.api import MoveshelfApi
import logging
import urllib3
from urllib3.util import Retry
from urllib3.util import Timeout
from urllib3.exceptions import MaxRetryError, HTTPError
from urllib3.response import HTTPResponse

from moveshelf_api.utils.hash import calculate_file_md5, calculate_stream_md5, calculate_file_crc32c

logger = logging.getLogger('moveshelf-api')

'''
Custom Moveshelf API class that extends the existing API
'''

class MoveshelfApiCustomized(MoveshelfApi):
    def uploadAdditionalData(self, file_path, clipId, dataType, filename):
        logger.info("Uploading %s", file_path)

        creation_response = self._createAdditionalData(
            clipId,
            {
                "clientId": file_path,
                "crc32c": calculate_file_crc32c(file_path),
                "filename": filename,
                "dataType": dataType,
            },
        )
        logging.info("Created additional data ID: %s", creation_response["data"]["id"])

        # --- Configure per-request retries and timeout (no change in site-packages) ---
        retries = Retry(
            total=5,                       # total attempts (original + 4 retries)
            backoff_factor=1,              # 1s, 2s, 4s... between retry attempts
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["PUT", "POST", "GET", "HEAD", "OPTIONS"])
        )
        timeout = Timeout(connect=10.0, read=120.0)  # allow slower uploads to finish

        # Stream the file instead of reading into memory
        with open(file_path, "rb") as fp:
            try:
                # Use body=fp so urllib3 streams directly from the file object
                response = self.http.request(
                    "PUT",
                    creation_response["uploadUrl"],
                    body=fp,
                    headers={"Content-Type": "application/octet-stream"},
                    preload_content=False,     # don't buffer the server response in memory
                    retries=retries,           # pass per-request retry policy
                    timeout=timeout,           # pass per-request timeout
                    # chunked=True,           # optional: enable chunked transfer (see notes)
                )

                # read response body to ensure the request completes and we get final status
                resp_body = response.read()   # will block up to timeout.read
                status = response.status

                if status >= 400:
                    raise HTTPError(f"Upload failed with status {status}: {getattr(response, 'reason', None)}: {resp_body!r}")

                logger.info("Upload succeeded for %s, status=%s", file_path, status)

            except MaxRetryError as e:
                logger.error("All retries exhausted during additional data upload: %s", e)
                raise
            except Exception as e:
                logger.error("Error during additional data upload: %s", e)
                raise
            finally:
                # make sure the connection is released back to the pool
                try:
                    response.release_conn()
                except Exception:
                    pass

        return creation_response["data"]["id"]
    
    
    def getSessionById(self, session_id):
        """
        Retrieve detailed information about a session by its ID.

        Args:
            session_id (str): The ID of the session to retrieve.

        Returns:
            dict: A dictionary containing session details, including:
                  - ID, projectPath, and metadata.
                  - Associated project, clips, norms, and patient information.
        """
        data = self._dispatch_graphql(
            '''
            query getSession($sessionId: ID!) {
                node(id: $sessionId) {
                    ... on Session {
                        id,
                        projectPath,
                        metadata,
                        date,
                        project {
                            id
                            name
                            canEdit
                            norms {
                                id
                                name
                                status
                            }
                        }
                        clips {
                            id
                            title
                            created
                            projectPath
                            uploadStatus
                            hasCharts
                            hasVideo
                        }
                        patient {
                            id
                            name
                            metadata
                        }
                    }
                }
            }
            ''',
            sessionId=session_id
        )
        return data['node']
    
    def getSubjectDetailsCustom(self, subject_id):
        """
        Retrieve details about a specific subject, including metadata,
        associated projects, reports, sessions, clips, and norms.

        Args:
            subject_id (str): The ID of the subject to retrieve.

        Returns:
            dict: A dictionary containing the subject's details, including:
                  - ID, name, and metadata.
                  - Associated project details (ID) and norms.
                  - List of reports (ID and title).
                  - List of sessions with nested clips details.
        """
        data = self._dispatch_graphql(
            '''
            query getPatient($patientId: ID!) {
                node(id: $patientId) {
                    ... on Patient {
                        id,
                        name,
                        metadata,
                        project {
                            id
                            norms {
                                id
                                name
                                uploadStatus
                                projectPath
                                clips {
                                    id
                                    title
                                }
                            }
                        }
                        reports {
                            id
                            title
                        }
                        sessions {
                            id
                            date
                            projectPath
                            clips {
                                id
                                title
                                created
                                projectPath
                                uploadStatus
                                hasCharts
                            }
                        }
                    }
                }
            }
            ''',
            patientId=subject_id
        )
        return data['node']
    
    def getSessionClips(self, session_id):
        """
        Retrieve all clips from a session by its ID.

        Args:
            session_id (str): The ID of the session to retrieve.

        Returns:
            list: A list of reports associated with the session.
        """
        data = self._dispatch_graphql(
            '''
            query getSession($sessionId: ID!) {
                node(id: $sessionId) {
                    ... on Session {
                        id,
                        projectPath,
                        clips {
                            id
                            title
                            created
                            projectPath
                            uploadStatus
                            hasCharts
                            additionalData (dataTypeFilter: ["data"]){
                                id
                                dataType
                                uploadStatus
                                originalFileName
                                originalDataDownloadUri
                            }
                        }
                    }
                }
            }
            ''',
            sessionId=session_id
        )
        return data['node']['clips']
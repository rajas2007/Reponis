from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RepositoryAvailable(BaseModel):
    github_repo_id: int
    owner: str
    name: str
    full_name: str
    visibility: str
    description: Optional[str] = None
    language: Optional[str] = None
    html_url: str


class RepositoriesAvailableResponse(BaseModel):
    repositories: List[RepositoryAvailable]


class RepositoryConnectRequest(BaseModel):
    github_repo_id: int


class RepositoryResponse(BaseModel):
    id: UUID
    github_repo_id: int
    full_name: str
    sync_status: str
    is_active: bool
    connected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoriesConnectedResponse(BaseModel):
    repositories: List[RepositoryResponse]


class RepositoryCurrentResponse(BaseModel):
    repository: Optional[RepositoryResponse]

# packages/contracts
# Shared Pydantic schemas and API contracts used across services.
from .tasks import (
    TaskCreate,
    TaskRead,
    TaskStatus,
    TaskUpdate,
    TaskListResponse,
)
from .users import UserContext, UserRole
from .common import APIResponse, ErrorDetail, PaginationParams
from .knowledge import (
    IngestRequest,
    IngestResponse,
    RetrieveRequest,
    RetrieveResponse,
    ChunkResult,
    ExtractRequest,
    ExtractResponse,
    EntityResult,
)
from .graph import (
    GraphEntity,
    GraphRelationship,
    GraphStoreRequest,
    GraphStoreResponse,
    GraphRetrieveRequest,
    GraphRetrieveResponse,
    GraphDeleteRequest,
)
from .mcp import (
    ToolInfo,
    ToolListResponse,
    ToolCallRequest,
    ToolCallResponse,
)

__all__ = [
    "TaskCreate",
    "TaskRead",
    "TaskStatus",
    "TaskUpdate",
    "TaskListResponse",
    "UserContext",
    "UserRole",
    "APIResponse",
    "ErrorDetail",
    "PaginationParams",
    "IngestRequest",
    "IngestResponse",
    "RetrieveRequest",
    "RetrieveResponse",
    "ChunkResult",
    "ExtractRequest",
    "ExtractResponse",
    "EntityResult",
    "GraphEntity",
    "GraphRelationship",
    "GraphStoreRequest",
    "GraphStoreResponse",
    "GraphRetrieveRequest",
    "GraphRetrieveResponse",
    "GraphDeleteRequest",
    "ToolInfo",
    "ToolListResponse",
    "ToolCallRequest",
    "ToolCallResponse",
]

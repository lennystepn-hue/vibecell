from pydantic import BaseModel, ConfigDict, Field

_SLUG_RE = r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$"


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    plan: str


class WorkspaceListItem(BaseModel):
    slug: str
    name: str
    role: str
    plan: str


class WorkspaceCreate(BaseModel):
    slug: str = Field(..., pattern=_SLUG_RE, min_length=2, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)

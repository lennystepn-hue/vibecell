from pydantic import BaseModel, ConfigDict, Field


class StackItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    kind: str | None = None
    icon_url: str | None = None


class StackItemCreate(BaseModel):
    slug: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9\-]{0,98}[a-z0-9]$",
        min_length=2,
        max_length=100,
    )
    name: str = Field(..., min_length=1, max_length=200)
    kind: str | None = Field(default=None, max_length=30)
    icon_url: str | None = Field(default=None, max_length=500)

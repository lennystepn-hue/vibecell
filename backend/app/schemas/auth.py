from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkAccepted(BaseModel):
    status: str = "accepted"

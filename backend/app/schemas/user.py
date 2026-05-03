from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    name: str | None = None
    handle: str | None = None
    # Admin-dashboard surfacing. Frontend uses is_admin to conditionally
    # render the /admin sidebar entry + route gate. totp_enabled drives
    # the 2FA setup card on /settings.
    is_admin: bool = False
    totp_enabled: bool = False

from pydantic import BaseModel


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan_tier: str
    lifecycle_status: str
    autonomy_mode: str

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    user_type: str

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    token: str
    user: UserResponse
    workspace: WorkspaceResponse


class DevLoginRequest(BaseModel):
    email: str
    name: str | None = None
    workspace_name: str | None = None


class WorkspaceCreate(BaseModel):
    name: str
    slug: str | None = None


class MembershipResponse(BaseModel):
    id: str
    role: str
    user: UserResponse

    class Config:
        from_attributes = True

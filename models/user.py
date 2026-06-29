from pydantic import BaseModel, EmailStr
from typing import Optional

class SignupRequest(BaseModel):
    name:     str
    email:    str
    password: str

class LoginRequest(BaseModel):
    email:    str
    password: str

class UserOut(BaseModel):
    id:         str
    name:       str
    email:      str
    role:       str          # 'admin' | 'customer'
    is_active:  bool
    created_at: float

class TokenResponse(BaseModel):
    token:      str
    user:       UserOut

class UpdateRoleRequest(BaseModel):
    role: str                # 'admin' | 'customer'

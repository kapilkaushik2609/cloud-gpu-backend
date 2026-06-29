from fastapi import APIRouter, HTTPException, Depends
from models.user import SignupRequest, LoginRequest, TokenResponse, UserOut
import services.auth_service as auth_svc
import services.storage as db

router = APIRouter()

def _to_out(u: dict) -> UserOut:
    return UserOut(id=u["id"], name=u["name"], email=u["email"],
                   role=u["role"], is_active=u["is_active"], created_at=u["created_at"])

@router.post("/signup", response_model=TokenResponse)
def signup(req: SignupRequest):
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user  = auth_svc.create_user(req.name.strip(), req.email.strip().lower(), req.password)
    token = auth_svc.create_token(user["id"], user["role"])
    return TokenResponse(token=token, user=_to_out(user))

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    user = db.find_user_by_email(req.email.strip().lower())
    if not user or not auth_svc.verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("is_active"):
        raise HTTPException(403, "Account is inactive")
    token = auth_svc.create_token(user["id"], user["role"])
    return TokenResponse(token=token, user=_to_out(user))

@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(auth_svc.get_current_user)):
    return _to_out(user)

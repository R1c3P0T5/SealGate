from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from src.auth.dependencies import get_current_user
from src.auth.schemas import (
    LoginResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from src.auth.service import authenticate_user, register_user
from src.core.database import SessionDep
from src.users.models import User
from src.users.service import build_user_response


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register user",
    description=(
        "Create a new active user account. Usernames must be unique, passwords "
        "must meet the configured strength policy, and emails are optional but "
        "must be unique when provided."
    ),
    response_description="The created user without password hash or face embedding data.",
)
async def register(
    request: UserRegisterRequest,
    session: SessionDep,
) -> UserResponse:
    user = await register_user(request, session)
    return await build_user_response(user, session)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login with JSON credentials",
    description=(
        "Authenticate an active user with a JSON username and password payload. "
        "Returns a bearer JWT plus the safe user profile for client session state."
    ),
    response_description="Bearer access token and authenticated user profile.",
)
async def login(
    request: UserLoginRequest,
    session: SessionDep,
) -> LoginResponse:
    user, token = await authenticate_user(request, session)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=await build_user_response(user, session),
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Issue OAuth2 access token",
    description=(
        "OAuth2 password flow endpoint for Swagger UI and OAuth2-compatible "
        "clients. Submit form-encoded username and password credentials."
    ),
    response_description="Bearer access token for Authorization headers.",
)
async def token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
) -> TokenResponse:
    user, token_value = await authenticate_user(
        UserLoginRequest(username=form_data.username, password=form_data.password),
        session,
    )
    return TokenResponse(access_token=token_value, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description=(
        "Return the profile associated with the bearer token in the "
        "Authorization header. Inactive or invalid-token users are rejected."
    ),
    response_description="The authenticated user's public profile.",
)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> UserResponse:
    return await build_user_response(current_user, session)

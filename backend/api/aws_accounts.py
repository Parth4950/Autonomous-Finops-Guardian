"""Authenticated, CSRF-protected endpoints for user-owned AWS account management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_aws_account_service
from backend.auth.dependencies import current_user
from backend.config.settings import CredentialsEncryptionError
from backend.db.session import get_db
from backend.models.auth import User
from backend.schemas.aws_accounts import (
    AWSAccountCreateRequest,
    AWSAccountResponse,
    AWSAccountUpdateRequest,
    AWSAccountVerifyRequest,
)
from backend.schemas.common import PaginatedResponse
from backend.services.aws_account_service import (
    AWSAccountConflictError,
    AWSAccountService,
)
from backend.utils.aws_client import AWSVerificationError
from backend.utils.credential_encryption import CredentialTamperError

router = APIRouter(prefix="/aws/accounts", tags=["AWS Accounts"])


@router.get(
    "",
    response_model=PaginatedResponse[AWSAccountResponse],
    summary="List connected AWS accounts",
)
def list_aws_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    service: AWSAccountService = Depends(get_aws_account_service),
) -> PaginatedResponse[AWSAccountResponse]:
    items = service.list_accounts(db, user.id)
    return PaginatedResponse[AWSAccountResponse](count=len(items), items=items)


@router.get(
    "/{account_id}",
    response_model=AWSAccountResponse,
    summary="Get a connected AWS account",
)
def get_aws_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    service: AWSAccountService = Depends(get_aws_account_service),
) -> AWSAccountResponse:
    try:
        return service.get_account(db, user.id, account_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "",
    response_model=AWSAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect and verify a user-owned AWS account",
)
def connect_aws_account(
    payload: AWSAccountCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    service: AWSAccountService = Depends(get_aws_account_service),
) -> AWSAccountResponse:
    try:
        return service.connect_account(db, user.id, payload)
    except AWSAccountConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (AWSVerificationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CredentialsEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post(
    "/{account_id}/verify",
    response_model=AWSAccountResponse,
    summary="Verify stored AWS credentials with STS GetCallerIdentity",
)
def verify_aws_account(
    account_id: int,
    payload: AWSAccountVerifyRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    service: AWSAccountService = Depends(get_aws_account_service),
) -> AWSAccountResponse:
    try:
        return service.verify_account(
            db,
            user.id,
            account_id,
            region=payload.region if payload else None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (AWSVerificationError, CredentialTamperError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CredentialsEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{account_id}",
    response_model=AWSAccountResponse,
    summary="Update AWS account metadata, region, or rotated credentials",
)
@router.put(
    "/{account_id}",
    response_model=AWSAccountResponse,
    include_in_schema=False,
)
def update_aws_account(
    account_id: int,
    payload: AWSAccountUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    service: AWSAccountService = Depends(get_aws_account_service),
) -> AWSAccountResponse:
    try:
        return service.update_account(db, user.id, account_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AWSAccountConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (AWSVerificationError, CredentialTamperError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CredentialsEncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a user-owned AWS account",
)
@router.post(
    "/{account_id}/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def disconnect_aws_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    service: AWSAccountService = Depends(get_aws_account_service),
) -> None:
    try:
        service.disconnect_account(db, user.id, account_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

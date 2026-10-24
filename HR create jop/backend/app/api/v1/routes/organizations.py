from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.schemas.organizations import OrganizationCreate, OrganizationResponse
from app.core.database import get_db
from app.services.organization_service import OrganizationService

router = APIRouter()


@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
def create_organization(body: OrganizationCreate, db: Session = Depends(get_db)):
    """Create a new organization.

    Bootstrap/development-only endpoint. Does NOT require X-User-Id or
    X-Organization-Id headers. NOT a production authentication or secure
    administrative endpoint.
    """
    return OrganizationService().create(db, name=body.name)

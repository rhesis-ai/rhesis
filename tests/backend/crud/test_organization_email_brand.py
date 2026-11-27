"""``load_organization_brand`` reads the branding an organization's email is sent with."""

import uuid

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.notifications.email.brand import OrganizationBrand
from rhesis.backend.notifications.email.organization_brand import load_organization_brand


def _brand(db: Session, organization_id: str, branding: dict) -> None:
    organization = db.get(models.Organization, organization_id)
    organization.settings.update(
        {
            "branding": {
                "product_name": None,
                "primary_color": None,
                "secondary_color": None,
                **branding,
            }
        }
    )
    db.flush()


@pytest.mark.integration
class TestLoadOrganizationBrand:
    def test_an_organization_without_branding_has_none(self, test_db: Session, test_org_id: str):
        _brand(test_db, test_org_id, {})

        assert load_organization_brand(test_db, test_org_id) is None

    def test_a_branded_organization_has_its_name_and_colours(
        self, test_db: Session, test_org_id: str
    ):
        _brand(
            test_db,
            test_org_id,
            {
                "product_name": "Acme Evals",
                "primary_color": "#6A1B9A",
                "secondary_color": "#FFD600",
            },
        )

        assert load_organization_brand(test_db, test_org_id) == OrganizationBrand(
            product_name="Acme Evals", primary_color="#6A1B9A", secondary_color="#FFD600"
        )

    def test_colours_apply_without_a_product_name(self, test_db: Session, test_org_id: str):
        _brand(test_db, test_org_id, {"primary_color": "#6A1B9A"})

        assert load_organization_brand(test_db, test_org_id) == OrganizationBrand(
            primary_color="#6A1B9A"
        )

    def test_no_organization_has_none(self, test_db: Session):
        assert load_organization_brand(test_db, None) is None
        assert load_organization_brand(test_db, uuid.uuid4()) is None

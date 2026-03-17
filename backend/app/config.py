import os
from pathlib import Path
from typing import Optional
from uuid import UUID

import yaml
from pydantic import BaseModel


class CompanyConfig(BaseModel):
    id: UUID
    name: str
    career_page_url: str
    linkedin_slug: Optional[str]
    active: bool
    use_linkedin: bool = False


def load_companies(yaml_path: Path) -> list[CompanyConfig]:
    """Parse and validate companies YAML. Raises ValueError on missing fields or invalid UUID."""
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    companies = []
    for entry in data.get("companies", []):
        try:
            company = CompanyConfig(**entry)
        except Exception as exc:
            raise ValueError(f"Invalid company entry {entry!r}: {exc}") from exc
        companies.append(company)
    return companies


# Path to companies.yaml — resolvable relative to backend/ directory.
# Can be overridden via COMPANIES_YAML_PATH environment variable.
_default_path = Path(__file__).parent.parent / "companies.yaml"
COMPANIES_YAML_PATH: Path = Path(os.getenv("COMPANIES_YAML_PATH", str(_default_path)))

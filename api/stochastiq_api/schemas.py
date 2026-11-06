"""Schémas pydantic d'entrée et de sortie.

Les schémas d'entrée refusent les champs inconnus (``extra="forbid"``).
"""

from datetime import datetime
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from .roles import Role


class Input(BaseModel):
    # Pas de nettoyage global des espaces : un mot de passe doit rester intact.
    model_config = ConfigDict(extra="forbid")


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _email(value: str) -> str:
    """Valide une adresse et la normalise en minuscules, sans vérification DNS.

    ``test_environment=True`` accepte le domaine réservé ``.test``, utilisé
    par les comptes de démonstration (``@example.test``).
    """
    try:
        result = validate_email(value, check_deliverability=False, test_environment=True)
    except EmailNotValidError as error:
        raise ValueError(f"Adresse e-mail invalide : {error}") from error
    return result.normalized.lower()


Email = Annotated[str, Field(max_length=254), AfterValidator(_email)]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RegisterIn(Input):
    email: Email
    name: Name
    password: str = Field(min_length=10, max_length=200)


class LoginIn(Input):
    email: Email
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(Output):
    id: int
    email: str
    name: str
    created_at: datetime


class ProjectIn(Input):
    name: Name
    description: str = Field(default="", max_length=2000)


class ProjectPatch(Input):
    name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)


class ProjectOut(Output):
    id: int
    name: str
    slug: str
    description: str
    created_by: int | None
    created_at: datetime
    role: Role


class MemberOut(BaseModel):
    user_id: int
    email: str
    name: str
    role: Role
    title: str
    created_at: datetime


class MemberPatch(Input):
    role: Role | None = None
    title: str | None = Field(default=None, max_length=50)


class InvitationIn(Input):
    email: Email
    role: Role


class InvitationOut(Output):
    id: int
    project_id: int
    email: str
    role: Role
    status: str
    expires_at: datetime
    created_at: datetime
    link: str


class InvitationPublic(BaseModel):
    project_name: str
    email: str
    role: Role
    status: str
    expires_at: datetime

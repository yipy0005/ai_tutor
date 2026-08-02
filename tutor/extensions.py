"""Shared Flask extension objects."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models."""


db = SQLAlchemy(model_class=Base)

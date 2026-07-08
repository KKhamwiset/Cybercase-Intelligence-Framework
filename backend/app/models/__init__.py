"""Models package — import all models here so Alembic can detect them."""
from app.models.case import CaseRecord  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.report import ReportRecord, ReportSessionRecord  # noqa: F401

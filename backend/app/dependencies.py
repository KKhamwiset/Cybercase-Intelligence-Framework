from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.report_workflow import ReportWorkflowService


def get_report_workflow_service(
    req: Request,
    db: AsyncSession = Depends(get_db),
) -> ReportWorkflowService:
    return ReportWorkflowService(
        report_gen=req.app.state.report_gen,
        db=db,
    )


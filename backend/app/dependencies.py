from fastapi import Request

from app.services.report_workflow import ReportWorkflowService


def get_report_workflow_service(req: Request) -> ReportWorkflowService:
    return ReportWorkflowService(
        report_gen=req.app.state.report_gen,
        report_store=req.app.state.report_store,
        report_sessions=req.app.state.report_sessions,
    )

from fastapi import APIRouter, HTTPException, status

from app.schemas.case_analysis import CaseAnalysisArtifact
from app.schemas.rag import CyberCaseReport


router = APIRouter(prefix="/reports", tags=["reports"])

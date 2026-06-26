from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from .schemas import CaseFactPack, ReportEntity


class LLMFactPackMixin:
    def _extract_case_fact_pack_with_llm(
        self,
        query: str,
        deterministic_pack: CaseFactPack,
        allowed_techniques: list[ReportEntity],
        legal: bool,
    ) -> CaseFactPack:
        if not self.fact_pack_llm:
            return deterministic_pack

        allowed_ids = [entity.attack_id for entity in allowed_techniques]
        prompt = self._build_fact_pack_prompt(
            query=query,
            deterministic_pack=deterministic_pack,
            allowed_ids=allowed_ids,
            legal=legal,
        )
        last_error = ""
        for _attempt in range(2):
            try:
                response = self.fact_pack_llm.invoke(
                    [
                        SystemMessage(
                            content=(
                                "You extract a strict CaseFactPack for cybercrime investigation support. "
                                "Use only the supplied evidence registry and allowed MITRE IDs. "
                                "Do not invent laws, facts, citations, dates, evidence IDs, or MITRE techniques."
                            )
                        ),
                        HumanMessage(content=prompt),
                    ]
                )
                pack = (
                    response
                    if isinstance(response, CaseFactPack)
                    else CaseFactPack.model_validate(response)
                )
                self.validate_case_fact_pack(pack, allowed_techniques, legal)
                return pack
            except (ValidationError, ValueError) as exc:
                last_error = str(exc)
                prompt += (
                    "\n\nThe previous JSON failed validation. Fix only the validation "
                    f"errors below and return the CaseFactPack schema again.\n{last_error}"
                )

        raise ValueError(f"Case Fact Pack validation failed after retry: {last_error}")


    def _build_fact_pack_prompt(
        self,
        query: str,
        deterministic_pack: CaseFactPack,
        allowed_ids: list[str],
        legal: bool,
    ) -> str:
        return (
            "Original case input:\n"
            f"{query}\n\n"
            "Deterministic starter CaseFactPack JSON:\n"
            f"{json.dumps(deterministic_pack.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"Allowed MITRE technique IDs from retrieval: {allowed_ids}\n"
            f"Legal mode enabled: {legal}\n\n"
            "Rules:\n"
            "- Extract only facts supported by the evidence registry or retrieved MITRE sources.\n"
            "- Every fact, indicator, timeline event, MITRE mapping, and legal note needs evidence_ids.\n"
            "- Missing facts stay in missing_information; do not infer dates or impact.\n"
            "- MITRE mappings must use only the allowed MITRE IDs.\n"
            "- If legal mode is false, legal_assessments must be empty.\n"
            "- If legal mode is true, use preliminary wording and include the required disclaimer exactly.\n"
        )

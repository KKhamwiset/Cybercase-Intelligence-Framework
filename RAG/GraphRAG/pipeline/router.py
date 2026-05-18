"""
Query Router
=================================
Classifies user queries to determine the appropriate processing pipeline.
"""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from config import ANTHROPIC_API_KEY, LLM_MODEL

ROUTER_SYSTEM_PROMPT = """You are a routing agent in a cybersecurity RAG system. Your responsibility is ONLY to classify the query and route it to the correct predefined processing pipeline. You must NOT redesign pipelines, modify workflow logic, or generate answers yourself.

The system already contains two existing downstream flows:

GENERAL_EXPLANATION
→ Route to the standard cybersecurity explanation pipeline (it may be can use by only using api calls and not retrieve anything just make the model answer upon it own knowledge)
INCIDENT_ANALYSIS
→ Route to the existing forensic RAG pipeline with:
retrieval → reasoning LLM → translation LLM

You must only decide which pipeline should receive the query.

Do NOT:
- redesign the workflow
- merge pipelines
- create new stages
- skip stages
- rewrite architecture
- answer the user query

Your task is routing only.

Classification rules:

GENERAL_EXPLANATION
Use when the user asks about cybersecurity concepts, terminology, definitions, tutorials, comparisons, or educational explanations.

Examples:
“SSH คืออะไร”
“TCP ต่างจาก UDP ยังไง”
“Malware คืออะไร”
“SQL injection คืออะไร”

These queries describe concepts, not incidents.

INCIDENT_ANALYSIS
Use when the query describes attacker actions, intrusion behavior, forensic narratives, attack chains, compromise activity, or operational cybersecurity incidents.

Examples:
“ผู้โจมตีเข้าระบบผ่าน SSH port 22”
“มีการยกระดับสิทธิ์ก่อนลบฐานข้อมูล”
“ติดตั้ง backdoor เพื่อคงอยู่ในระบบ”

These queries describe events or attack activity.

Routing rules:
- If the query describes a sequence of attacker actions, use INCIDENT_ANALYSIS
- If the query asks for knowledge or explanation only, use GENERAL_EXPLANATION
- If uncertain, classify based on:
  “concept/question” → GENERAL_EXPLANATION
  “event/activity” → INCIDENT_ANALYSIS

Output rules:
Return ONLY one label
Valid outputs:
GENERAL_EXPLANATION
INCIDENT_ANALYSIS"""

class QueryRouter:
    def __init__(self):
        if not ANTHROPIC_API_KEY:
            self.llm = None
        else:
            self.llm = ChatAnthropic(
                model=LLM_MODEL,
                api_key=ANTHROPIC_API_KEY,
                temperature=0,
                max_tokens=32,
            )

    def route_query(self, query: str) -> str:
        """Classify the user query as GENERAL_EXPLANATION or INCIDENT_ANALYSIS."""
        if not self.llm:
            # Fallback to INCIDENT_ANALYSIS if no LLM
            return "INCIDENT_ANALYSIS"

        response = self.llm.invoke([
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=query)
        ])
        
        result = response.content.strip()
        # Clean up in case the model adds extra text
        if "GENERAL_EXPLANATION" in result:
            return "GENERAL_EXPLANATION"
        return "INCIDENT_ANALYSIS"

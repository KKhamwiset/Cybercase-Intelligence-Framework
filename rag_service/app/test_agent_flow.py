"""
Follow-up trigger test: queries that are intentionally vague so the
evaluator should return INSUFFICIENT and ask a clarifying question.
A simulated followup_callback provides a pre-written answer so the
full follow-up → re-retrieve → answer loop can be observed.
"""
import sys
import io

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# (query, simulated_followup_answer)
TEST_CASES = [
    (
        # Vague — no specific technique, only outcome described
        "ผู้ต้องหาแฮกเข้าระบบบริษัทและขโมยข้อมูลลูกค้าออกไปทั้งหมด",
        "ผู้ต้องหาส่งอีเมลหลอกพนักงานฝ่าย HR ให้กดลิ้งก์ แล้วกรอก username/password บนหน้าเว็บปลอม",
    ),
    (
        # Missing initial access — only shows post-compromise action
        "ผู้ต้องหาได้รับสิทธิ์ administrator แล้วติดตั้ง backdoor และลบ log ทิ้งทั้งหมด",
        "ใช้ brute force โจมตี SSH port ที่เปิดไว้จนได้รหัสผ่าน",
    ),
    (
        # Vague lateral movement + ransomware, no initial vector
        "มีการบุกรุกเครือข่ายภายในองค์กรแล้วแพร่กระจาย ransomware ไปทุกเครื่อง",
        "ผู้โจมตีเชื่อมต่อผ่าน VPN ที่ใช้ credential ที่รั่วไหลจากบริษัทอื่น",
    ),
]


def make_callback(simulated_answer: str):
    """Return a followup_callback that always answers with the pre-written string."""
    called = {"count": 0}

    def callback(question: str) -> str:
        called["count"] += 1
        print(f"\n  [SIMULATED ANSWER #{called['count']}]: {simulated_answer}")
        return simulated_answer

    return callback


if __name__ == "__main__":
    from RAG.GraphRAG.pipeline.agent_graph import GraphRAGAgent
    from RAG.GraphRAG.config import sep

    agent = GraphRAGAgent()

    for i, (query, answer) in enumerate(TEST_CASES, 1):
        sep(f"TEST CASE {i}/{len(TEST_CASES)}")
        print(f"  Query  : {query}")
        print(f"  Answer : {answer}\n")

        response = agent.query(
            query,
            verbose=True,
            followup_callback=make_callback(answer),
        )

        sep(f"FINAL RESULT {i}")
        print(f"  Status : {response.status}")
        if response.status == "followup":
            print(f"  [NOTE] Pipeline paused — follow-up not answered (no callback hit)")
            print(f"  Follow-up: {response.followup_question}")
        else:
            print(f"  Answer (first 600 chars):\n")
            print(f"  {response.answer[:600]}")

    agent.close()
    print("\n\nDone.")

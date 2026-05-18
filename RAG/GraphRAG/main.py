"""
MITRE ATT&CK GraphRAG — CLI Entrypoint
========================================
Usage:
    python main.py --ingest       # Parse STIX data → load Neo4j + ChromaDB
    python main.py --test          # Run test queries
    python main.py                 # Interactive mode
    python main.py --retrieve-only # Retrieval without LLM (for debugging)
"""

import argparse
import io
import sys

from config import (
    CHROMA_DIR,
    EMBED_MODEL,
    sep,
)
from sentence_transformers import SentenceTransformer

# ──────────────────────────────────────────────────────────────────────────────
# UTF-8 FIX FOR WINDOWS
# ──────────────────────────────────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ──────────────────────────────────────────────────────────────────────────────
# INGEST
# ──────────────────────────────────────────────────────────────────────────────
def run_ingest():
    """Parse STIX data and load into Neo4j + ChromaDB."""
    from ingestion.graph_loader import GraphLoader
    from ingestion.stix_parser import parse_all_domains
    from ingestion.vector_loader import VectorLoader

    sep("STIX PARSING")

    parser = parse_all_domains()

    # Load into Neo4j
    sep("NEO4J INGESTION")
    graph_loader = GraphLoader()
    try:
        graph_loader.load_all(parser)
    finally:
        graph_loader.close()

    # Load into ChromaDB
    sep("CHROMADB INGESTION")
    print(f"[EMBED] Loading {EMBED_MODEL}...")
    embed_model = SentenceTransformer(EMBED_MODEL)

    vector_loader = VectorLoader(embed_model=embed_model)
    vector_loader.load_all(parser)

    sep("INGESTION COMPLETE")
    print("✓ Neo4j: Graph loaded with nodes + edges")
    print("✓ ChromaDB: Entity + relationship embeddings stored")
    print(f"✓ ChromaDB path: {CHROMA_DIR}")


# ──────────────────────────────────────────────────────────────────────────────
# TEST
# ──────────────────────────────────────────────────────────────────────────────
TEST_QUERIES = [
    # Thai queries
    "ผู้ต้องหาใช้ SQL Injection เจาะระบบเว็บแอปพลิเคชันขององค์กรผ่านช่องกรอกข้อมูลที่ไม่ปลอดภัย ทำให้สามารถเข้าถึงฐานข้อมูลลูกค้า ดาวน์โหลดข้อมูลส่วนบุคคล และแก้ไขข้อมูลบางส่วน ส่งผลให้เกิดความเสียหายต่อความน่าเชื่อถือและทรัพย์สินข้อมูลของบริษัท",
    "ผู้ต้องหาใช้พอร์ต 80 ซึ่งเป็นช่องทาง HTTP ปกติในการส่ง payload โจมตีเว็บเซิร์ฟเวอร์ขององค์กร ใช้ช่องโหว่ใน web service ทำให้ระบบล่มชั่วคราวและไม่สามารถให้บริการลูกค้าได้",
    "ผู้ต้องหาใช้เทคนิค Social Engineering หลอกพนักงานผ่านอีเมลปลอมอ้างฝ่าย IT ให้กดไฟล์แนบที่มีมัลแวร์ ส่งผลให้เครื่องพนักงานถูกควบคุมและข้อมูลภายในถูกดึงออกไป",
    "ผู้ต้องหาเชื่อมต่อเข้าสู่ระบบภายในผ่าน WiFi องค์กรที่ไม่มีการตั้งรหัสผ่านหรือใช้รหัสอ่อน จากนั้นสแกนหาเครื่องภายในและเข้าถึงข้อมูลสำคัญของฝ่ายบัญชี",
    "ผู้ต้องหาใช้ Phishing Email ปลอมเป็นระบบยืนยันตัวตนขององค์กร หลอกให้ผู้ใช้กรอก username และ password ส่งผลให้บัญชีผู้ดูแลระบบถูกยึดและนำไปใช้งานต่อ",
    "ผู้ต้องหาใช้ USB ที่ฝังมัลแวร์เสียบเข้ากับเครื่อง Server ในห้อง Data Center ทำให้เกิดการติดตั้ง backdoor และมีการดึงข้อมูลสำคัญออกไปยังภายนอก",
    "ผู้ต้องหาใช้ API Request Flooding ยิงคำขอจำนวนมากเข้าสู่ระบบ API ขององค์กร ทำให้เกิดภาวะ Denial of Service ส่งผลให้บริการออนไลน์หยุดชะงัก",
    "ผู้ต้องหาใช้ Remote Desktop Protocol ที่ตั้งค่าความปลอดภัยต่ำและใช้รหัสผ่านอ่อน เข้าควบคุมเครื่องพนักงานจากระยะไกลและติดตั้งโปรแกรมขโมยข้อมูล",
    "ผู้ต้องหาใช้ Credential ที่รั่วไหลจากเว็บไซต์อื่น (credential reuse) เข้าสู่ระบบองค์กรโดยไม่ต้องเจาะระบบใหม่ จากนั้นดาวน์โหลดไฟล์สำคัญจำนวนมาก",
    "ผู้ต้องหาใช้เทคนิค Man-in-the-Middle ดักจับข้อมูลระหว่างผู้ใช้กับเซิร์ฟเวอร์ผ่านเครือข่ายที่ไม่เข้ารหัส และแก้ไขข้อมูลธุรกรรมบางรายการระหว่างทาง",
    "ผู้ต้องหาใช้ช่องโหว่ CMS เวอร์ชันเก่าเจาะระบบเว็บไซต์ อัปโหลด web shell เพื่อควบคุม server จากระยะไกลและสั่งรันคำสั่งระบบได้ทั้งหมด",
    "ผู้ต้องหาแอบติดตั้ง keylogger ในเครื่องพนักงานเพื่อบันทึกการกดแป้นพิมพ์ ทำให้ได้รหัสผ่านและข้อมูลสำคัญก่อนส่งออกไปยังเซิร์ฟเวอร์ภายนอก",
    "ผู้ต้องหาแฝงตัวเป็นช่างเทคนิคเข้าไปในอาคารสำนักงาน ใช้ Social Engineering หลอกเจ้าหน้าที่รักษาความปลอดภัยเพื่อเข้าห้อง Server และติดตั้งอุปกรณ์ดักข้อมูล",
    "ผู้ต้องหาใช้ช่องโหว่ Zero-day ของระบบปฏิบัติการเพื่อยกระดับสิทธิ์จากผู้ใช้ทั่วไปเป็น Administrator และเข้าถึงไฟล์ที่ถูกจำกัดสิทธิ์",
    "ผู้ต้องหาใช้ Token การเข้าถึงระบบ Cloud ที่รั่วไหลจาก repository สาธารณะ เข้าดาวน์โหลดข้อมูลจาก storage ขององค์กรโดยไม่ได้รับอนุญาต",
    "ผู้ต้องหาใช้วิธี Brute Force ยิงรหัสผ่าน SSH อย่างต่อเนื่องจนสามารถเข้าควบคุม Linux Server ขององค์กรและติดตั้ง backdoor ถาวร",
    "ผู้ต้องหาใช้ Email Spoofing ปลอมอีเมลผู้บริหารระดับสูง สั่งให้ฝ่ายการเงินโอนเงินไปบัญชีปลายทาง ส่งผลให้เกิดความเสียหายทางการเงินจำนวนมาก",
    "ผู้ต้องหาใช้ Ransomware เข้ารหัสไฟล์ทั้งหมดในระบบองค์กร ทำให้ไม่สามารถเข้าถึงข้อมูลได้ และเรียกค่าไถ่เพื่อแลกกับการถอดรหัส",
    "ผู้ต้องหาใช้ DNS Spoofing หลอกผู้ใช้ให้เข้าเว็บไซต์ปลอมที่มีหน้าตาเหมือนของจริง เพื่อขโมยข้อมูลล็อกอินและ session token",
    "ผู้ต้องหาใช้ Firewall misconfiguration ในการ bypass ระบบป้องกัน ทำให้สามารถเข้าถึงระบบภายในที่ควรจะถูกปิดกั้นได้",
    "ผู้ต้องหาใช้ script อัตโนมัติสแกน port ภายในระบบองค์กรเพื่อค้นหาบริการที่เปิดอยู่ และใช้ exploit เข้าควบคุมเครื่องเป้าหมาย",
    "ผู้ต้องหาโทรหลอก Helpdesk โดยอ้างเป็นพนักงานจริง ขอ reset password และใช้บัญชีที่ได้มาเข้าระบบภายในองค์กร",
    "ผู้ต้องหาแอบฝัง backdoor ใน pipeline การ deploy software ทำให้ทุก version ที่ถูก deploy มีช่องทางลับในการเข้าถึงระบบ",
    "ผู้ต้องหาใช้ไฟล์ Excel ที่ฝัง macro อันตราย ส่งให้พนักงานเปิดใช้งาน เมื่อกด enable macro จะติด malware ทันที",
    "ผู้ต้องหาใช้ช่องโหว่ File Upload ในเว็บไซต์องค์กร อัปโหลด script อันตรายและสั่งให้ server execute code จากภายนอก",
    "ผู้ต้องหาใช้ packet sniffing ในเครือข่ายภายในที่ไม่มีการเข้ารหัส ดักจับ username และ password ของระบบ internal service",
    "ผู้ต้องหาเป็น insider ภายในองค์กร ทำการคัดลอกฐานข้อมูลลูกค้าออกไปผ่าน external drive โดยไม่มีการตรวจจับ",
    "ผู้ต้องหาใช้ fake login page ที่เหมือนระบบจริงอย่างมาก หลอกให้พนักงานกรอกข้อมูล credential แล้วส่งกลับไปยัง server ของผู้โจมตี",
    "ผู้ต้องหาใช้ session hijacking ขโมย session cookie ของผู้ใช้งานที่ login อยู่ แล้วเข้าใช้งานระบบแทนผู้ใช้จริง",
    "ผู้ต้องหาใช้ botnet ขนาดใหญ่ยิง traffic เข้าสู่เว็บไซต์องค์กรอย่างต่อเนื่อง ทำให้ระบบล่มและไม่สามารถให้บริการได้",
]


def run_tests(retrieve_only: bool = False):
    """Run test queries."""
    from pipeline.chain import GraphRAGChain

    chain = GraphRAGChain()

    sep("TEST SUITE")
    print(f"Running {len(TEST_QUERIES)} test queries")
    print(f"Mode: {'retrieve-only' if retrieve_only else 'full pipeline'}")

    try:
        for i, query in enumerate(TEST_QUERIES, 1):
            print(f"\n{'=' * 72}")
            print(f"  TEST {i}/{len(TEST_QUERIES)}")
            print(f"{'=' * 72}")

            if retrieve_only:
                context = chain.retrieve_only(query)
                sep("RETRIEVED CONTEXT")
                print(context[:2000])
                sep()
            else:
                chain.query(query, verbose=True)
    finally:
        chain.close()


# ──────────────────────────────────────────────────────────────────────────────
# INTERACTIVE
# ──────────────────────────────────────────────────────────────────────────────
def run_interactive(retrieve_only: bool = False):
    """Interactive query mode."""
    from pipeline.chain import GraphRAGChain

    chain = GraphRAGChain()

    mode = "RETRIEVE-ONLY" if retrieve_only else "FULL PIPELINE"

    print(f"\n{'=' * 72}")
    print(f"  MITRE ATT&CK GraphRAG — Interactive Mode ({mode})")
    print("  Type 'quit' or 'q' to exit")
    print("  Supports Thai and English queries")
    print(f"{'=' * 72}")

    try:
        while True:
            try:
                query = input("\n🔍 Query> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nBye!")
                break

            if query.lower() in ("exit", "quit", "q"):
                print("Bye!")
                break

            if not query:
                continue

            if retrieve_only:
                context = chain.retrieve_only(query)
                sep("RETRIEVED CONTEXT")
                print(context[:3000])
                sep()
            else:
                chain.query(query, verbose=True)
    finally:
        chain.close()


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    arg_parser = argparse.ArgumentParser(
        description="MITRE ATT&CK GraphRAG Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --ingest          # Load data into Neo4j + ChromaDB
  python main.py --test            # Run test queries (full pipeline)
  python main.py --test --retrieve-only  # Test retrieval without LLM
  python main.py                   # Interactive mode
        """,
    )

    arg_parser.add_argument(
        "--ingest",
        action="store_true",
        help="Parse STIX data and load into Neo4j + ChromaDB",
    )

    arg_parser.add_argument(
        "--test",
        action="store_true",
        help="Run test queries",
    )

    arg_parser.add_argument(
        "--retrieve-only",
        action="store_true",
        help="Retrieval without LLM generation (for debugging)",
    )

    args = arg_parser.parse_args()

    if args.ingest:
        run_ingest()
    elif args.test:
        run_tests(retrieve_only=args.retrieve_only)
    else:
        run_interactive(retrieve_only=args.retrieve_only)


if __name__ == "__main__":
    main()

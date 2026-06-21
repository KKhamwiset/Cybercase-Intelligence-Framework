"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { CyberCaseReport, generateReport } from "@/lib/api";

const SAMPLE_CASE = `ผู้เสียหายได้รับอีเมลแจ้งให้กดยืนยันบัญชีธนาคารผ่านลิงก์ปลอม หลังจากกรอกข้อมูล มีรายการโอนเงินออกจากบัญชีโดยไม่ได้รับอนุญาต พบโดเมนต้องสงสัยและ IP ที่ใช้เชื่อมต่อจากต่างประเทศ`;

type ReportSectionProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
};

function ReportSection({ title, subtitle, children }: ReportSectionProps) {
  return (
    <section className="card p-6">
      <div className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-secondary">
          {subtitle}
        </p>
        <h2 className="mt-1 text-xl font-bold text-primary">{title}</h2>
      </div>
      <div className="text-sm leading-7 text-neutral">{children}</div>
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p>ยังไม่มีข้อมูลในส่วนนี้</p>;
  }

  return (
    <ul className="space-y-3">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="flex gap-3">
          <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-secondary" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export default function ReportPage() {
  const [query, setQuery] = useState("");
  const [report, setReport] = useState<CyberCaseReport | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  const canSubmit = useMemo(
    () => query.trim().length > 20 && !isGenerating,
    [query, isGenerating],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      setError("กรุณาใส่รายละเอียดคดีก่อนสร้างรายงาน");
      return;
    }

    setIsGenerating(true);
    setError("");

    try {
      const result = await generateReport(trimmedQuery);
      setReport(result);
    } catch (generationError) {
      console.error(generationError);
      setError(
        "สร้างรายงานไม่สำเร็จ กรุณาตรวจสอบ backend/RAG service และลองใหม่อีกครั้ง",
      );
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <nav className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-5 lg:px-12">
        <Link
          href="/"
          className="flex items-center gap-3 text-xl font-bold tracking-tight text-primary"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded bg-primary text-sm text-white">
            C
          </div>
          CyberCase Framework
        </Link>
        <div className="flex items-center gap-4 text-sm font-medium">
          <Link href="/chat" className="text-neutral hover:text-primary">
            RAG Search
          </Link>
          <Link href="/report" className="text-primary">
            Report Generation
          </Link>
        </div>
      </nav>

      <section className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="space-y-6">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-secondary">
                Preliminary Cyber Case Report
              </p>
              <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-primary lg:text-5xl">
                Generate an evidence-grounded cyber case draft
              </h1>
              <p className="mt-4 text-base leading-8 text-neutral">
                สร้างร่างรายงานวิเคราะห์คดีไซเบอร์เบื้องต้นจากรายละเอียดคดี
                พร้อม MITRE ATT&CK mapping, เหตุผลจากหลักฐาน, ข้อจำกัด และขั้นตอนตรวจสอบต่อสำหรับมนุษย์
              </p>
            </div>

            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm leading-7 text-amber-900">
              <strong>Human review required:</strong> รายงานนี้เป็นเพียงร่างวิเคราะห์เบื้องต้น
              ไม่ใช่คำวินิจฉัยทางกฎหมายขั้นสุดท้าย และไม่แทนที่การตรวจสอบของอัยการ/ผู้เชี่ยวชาญ
            </div>
          </div>

          <form onSubmit={handleSubmit} className="card flex flex-col gap-5 p-6">
            <label htmlFor="case-detail" className="text-sm font-semibold text-primary">
              Case details / รายละเอียดคดี
            </label>
            <textarea
              id="case-detail"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="ใส่รายละเอียดเหตุการณ์ เช่น วิธีหลอกลวง หลักฐานที่พบ log, IP, domain, timeline, ความเสียหาย..."
              className="min-h-64 resize-y rounded-xl border border-gray-200 bg-white p-4 text-sm leading-7 text-primary outline-none transition focus:border-secondary focus:ring-2 focus:ring-secondary/20"
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={() => setQuery(SAMPLE_CASE)}
                className="btn-outlined"
              >
                Use sample case
              </button>
              <button
                type="submit"
                disabled={!canSubmit}
                className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isGenerating ? "Generating..." : "Generate Report"}
              </button>
            </div>
            {error ? (
              <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {error}
              </p>
            ) : null}
          </form>
        </div>

        {report ? (
          <div className="grid gap-5">
            <ReportSection title="Case Summary" subtitle="5.1 สรุปคดี">
              <p>{report.case_summary}</p>
            </ReportSection>

            <ReportSection
              title="Detected Indicators / Artifacts"
              subtitle="5.2 ตัวบ่งชี้ที่พบ"
            >
              <BulletList items={report.detected_indicators} />
            </ReportSection>

            <ReportSection title="MITRE ATT&CK Mapping" subtitle="5.3 เทคนิคที่เกี่ยวข้อง">
              <BulletList items={report.mitre_mapping} />
            </ReportSection>

            <ReportSection
              title="Evidence-Based Justification"
              subtitle="5.4 เหตุผลของการ mapping"
            >
              <p>{report.mapping_justification}</p>
            </ReportSection>

            <ReportSection
              title="Evidence to Investigate / Validate"
              subtitle="5.5 หลักฐานที่ควรตรวจสอบ"
            >
              <BulletList items={report.evidence_to_investigate} />
            </ReportSection>

            <ReportSection
              title="Preliminary Recommendations"
              subtitle="5.6 คำแนะนำเบื้องต้น"
            >
              <BulletList items={report.preliminary_recommendations} />
            </ReportSection>

            <ReportSection title="System Limitations" subtitle="5.7 ข้อจำกัดของระบบ">
              <p>{report.system_limitations}</p>
            </ReportSection>
          </div>
        ) : null}
      </section>
    </main>
  );
}

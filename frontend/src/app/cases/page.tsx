"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import CyberCaseShell from "@/components/CyberCaseShell";
import { useCases, useCreateCase } from "@/hooks/useCase";

export default function CasesPage() {
  const router = useRouter();
  const casesQuery = useCases();
  const createMutation = useCreateCase();
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    try {
      const createdCase = await createMutation.mutateAsync({
        title: title.trim() || "Untitled case",
      });
      router.push(`/cases/${createdCase.case_id}/intake`);
    } catch {
      setError("Could not create the case.");
    }
  };

  return (
    <CyberCaseShell activeNav="Investigate" title="Cases" subtitle="Saved investigations">
      <div className="h-full overflow-auto bg-neutral-100 p-5">
        <div className="mx-auto grid max-w-6xl gap-5 lg:grid-cols-[360px_1fr]">
          <form onSubmit={handleCreate} className="border border-black/10 bg-white p-5">
            <p className="mono-label">New case</p>
            <h1 className="mt-2 text-2xl font-black">Create investigation</h1>
            <label htmlFor="case-title" className="mt-5 block text-xs font-black uppercase text-neutral">
              Case title
            </label>
            <input
              id="case-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="mt-2 w-full border border-black/15 px-3 py-3 text-sm font-semibold outline-none focus:border-black"
              placeholder="Phishing credential theft"
            />
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="btn-primary mt-4 w-full"
            >
              {createMutation.isPending ? "Creating" : "Create Case"}
            </button>
            {error ? <p className="mt-3 text-sm font-semibold text-red-700">{error}</p> : null}
          </form>

          <section className="border border-black/10 bg-white p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="mono-label">Case list</p>
                <h2 className="mt-1 text-xl font-black">Saved cases</h2>
              </div>
            </div>

            {casesQuery.isLoading ? (
              <p className="mt-5 text-sm font-semibold text-neutral">Loading cases.</p>
            ) : null}
            {casesQuery.error ? (
              <p className="mt-5 text-sm font-semibold text-red-700">
                Could not load saved cases.
              </p>
            ) : null}
            {casesQuery.data?.length ? (
              <div className="mt-5 divide-y divide-black/10 border border-black/10">
                {casesQuery.data.map((caseItem) => (
                  <Link
                    key={caseItem.case_id}
                    href={`/cases/${caseItem.case_id}/intake`}
                    className="grid gap-2 p-4 transition hover:bg-neutral-100 md:grid-cols-[1fr_120px_120px]"
                  >
                    <div>
                      <p className="font-black">{caseItem.title}</p>
                      <p className="mt-1 text-xs font-semibold text-neutral">
                        {caseItem.case_id}
                      </p>
                    </div>
                    <p className="text-xs font-black uppercase">{caseItem.status}</p>
                    <p className="text-xs font-black uppercase">{caseItem.severity}</p>
                  </Link>
                ))}
              </div>
            ) : null}
            {casesQuery.data && casesQuery.data.length === 0 ? (
              <p className="mt-5 text-sm font-semibold text-neutral">
                No saved cases yet.
              </p>
            ) : null}
          </section>
        </div>
      </div>
    </CyberCaseShell>
  );
}

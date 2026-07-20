"use client";

export type CaseTab = "Inbox" | "Active" | "Archived";

export type InvestigationCaseRow = {
  name: string;
  owner: string;
  time: string;
  active: boolean;
  preview: string;
};

export const CASE_TABS: CaseTab[] = ["Inbox", "Active", "Archived"];

type InvestigationCaseListProps = {
  activeTab: CaseTab;
  caseRows: InvestigationCaseRow[];
  onActiveTabChange: (tab: CaseTab) => void;
};

export default function InvestigationCaseList({
  activeTab,
  caseRows,
  onActiveTabChange,
}: InvestigationCaseListProps) {
  return (
    <aside className="hidden min-h-0 flex-col border-r border-black/10 bg-white lg:flex">
      <div className="border-b border-black/10 p-4">
        <label htmlFor="case-search" className="sr-only">
          Search cases
        </label>

        <input
          id="case-search"
          type="search"
          placeholder="Search cases"
          className="w-full border border-black/10 bg-neutral-50 px-3 py-2 text-sm outline-none placeholder:text-neutral focus:border-black"
        />

        <div className="mt-3 grid grid-cols-3 gap-1 rounded-md bg-neutral-100 p-1">
          {CASE_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => onActiveTabChange(tab)}
              className={`rounded px-2 py-1.5 text-[11px] font-black ${
                activeTab === tab
                  ? "bg-white text-black shadow-sm"
                  : "text-neutral"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="space-y-2">
          {caseRows.map((item) => (
            <button
              key={item.name}
              type="button"
              className={`w-full rounded-lg border p-3 text-left transition ${
                item.active
                  ? "border-black bg-neutral-50"
                  : "border-transparent bg-white hover:border-black/10 hover:bg-neutral-50"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-black">{item.name}</p>
                  <p className="mt-1 truncate text-[11px] font-semibold text-neutral">
                    {item.owner}
                  </p>
                </div>

                <span className="shrink-0 text-[11px] font-semibold text-neutral">
                  {item.time}
                </span>
              </div>

              <p className="mt-3 line-clamp-2 text-xs leading-5 text-neutral">
                {item.preview}
              </p>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}

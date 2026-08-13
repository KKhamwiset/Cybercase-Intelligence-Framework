import Link from "next/link";
import type { CaseInformationRouteView } from "./types";

interface CaseInformationRouteHeaderProps {
  threadId: string;
  activeView: CaseInformationRouteView;
}

const caseInformationRoutes: Array<{
  view: CaseInformationRouteView;
  label: string;
  description: string;
}> = [
  {
    view: "extraction",
    label: "Case information",
    description: "Reported case information and entities",
  },
  {
    view: "timeline",
    label: "Timeline",
    description: "Reported event sequence",
  },
  {
    view: "relationships",
    label: "Relationships",
    description: "Source-grounded candidate relationship graph",
  },
];

function caseInformationPath(
  threadId: string,
  view: CaseInformationRouteView,
): string {
  return `/chat/${encodeURIComponent(threadId)}/${view}`;
}

export function CaseInformationRouteHeader({
  threadId,
  activeView,
}: CaseInformationRouteHeaderProps) {
  return (
    <nav
      aria-label="Reported case-information views"
      className="overflow-x-auto border-b border-[#DEDCD5] bg-[#F7F6F2]"
    >
      <div className="flex min-w-max gap-1 px-4 py-2 sm:px-7 lg:px-10">
        {caseInformationRoutes.map(({ view, label, description }) => {
          const selected = view === activeView;
          return (
            <Link
              key={view}
              href={caseInformationPath(threadId, view)}
              aria-current={selected ? "page" : undefined}
              title={description}
              className={`inline-flex min-h-11 items-center rounded-xl border px-4 text-sm font-bold outline-none transition-[background-color,border-color,color] duration-150 focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 motion-reduce:transition-none ${
                selected
                  ? "border-[#171717] bg-[#171717] text-white"
                  : "border-transparent text-[#6B6A66] hover:border-[#C9C7BF] hover:bg-[#FCFBF8] hover:text-[#171717]"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

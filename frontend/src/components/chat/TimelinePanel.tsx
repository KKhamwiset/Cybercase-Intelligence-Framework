import type { ReactNode } from "react";
import type { InspectorSelection } from "./types";

interface TimelinePanelProps {
  events: string[];
  inlineInspector: ReactNode;
  onSelect: (selection: InspectorSelection) => void;
}

export function TimelinePanel({
  events,
  inlineInspector,
  onSelect,
}: TimelinePanelProps) {
  return (
    <section
      id="timeline-panel"
      role="tabpanel"
      aria-labelledby="vertical-timeline-tab horizontal-timeline-tab"
      className="h-full overflow-y-auto bg-white px-4 py-6 sm:px-6 lg:px-8"
    >
      <div className="mx-auto max-w-4xl">
        <header className="border-b border-gray-200 pb-5">
          <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-gray-500">
            Returned events only
          </p>
          <h2 className="mt-2 text-2xl font-extrabold tracking-tight">Timeline</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
            Event text and ordering are shown exactly as returned. CyberCase does
            not infer missing dates here.
          </p>
        </header>

        {events.length === 0 ? (
          <p className="py-12 text-sm text-gray-600">
            No timeline events were returned.
          </p>
        ) : (
          <ol className="border-l border-gray-300 py-4 pl-6">
            {events.map((event, index) => (
              <li key={`${event}-${index}`} className="relative py-3">
                <span className="absolute -left-[29px] top-6 h-2.5 w-2.5 rounded-full border-2 border-white bg-black ring-1 ring-gray-300" />
                <button
                  type="button"
                  onClick={() =>
                    onSelect({ kind: "timeline", item: event, index })
                  }
                  className="w-full rounded-xl border border-gray-200 bg-white px-4 py-4 text-left text-sm leading-6 text-gray-800 outline-none transition-colors hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 motion-reduce:transition-none"
                >
                  <span className="mb-1 block font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-gray-500">
                    Returned event {index + 1}
                  </span>
                  {event}
                </button>
              </li>
            ))}
          </ol>
        )}

        <div className="mt-8 min-[1100px]:hidden">{inlineInspector}</div>
      </div>
    </section>
  );
}

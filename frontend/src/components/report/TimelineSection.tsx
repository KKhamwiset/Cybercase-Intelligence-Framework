import type { ReportSection as ReportSectionView, TimelineEventView } from "@/lib/reports";
import ReportSection from "./ReportSection";
import { FindingStatusBadge } from "./status";

function isTimelineEvent(value: unknown): value is TimelineEventView {
  return typeof value === "object" && value !== null && "event_id" in value && "title" in value;
}

export default function TimelineSection({ section }: { section: ReportSectionView }) {
  const events = Array.isArray(section.content.events)
    ? section.content.events.filter(isTimelineEvent)
    : [];

  return (
    <ReportSection section={section}>
      {events.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] border-collapse text-left text-sm">
            <thead className="border-b border-black/15 text-[10px] font-black uppercase text-neutral">
              <tr>
                <th className="py-2 pr-3">Time</th>
                <th className="py-2 pr-3">Event</th>
                <th className="py-2 pr-3">Evidence</th>
                <th className="py-2 pr-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.event_id} className="border-b border-black/10">
                  <td className="py-3 pr-3 font-semibold">{event.timestamp ?? "Unknown"}</td>
                  <td className="py-3 pr-3">
                    <p className="font-black">{event.title}</p>
                    {event.description ? (
                      <p className="mt-1 text-xs text-neutral">{event.description}</p>
                    ) : null}
                  </td>
                  <td className="py-3 pr-3 text-xs font-semibold">
                    {event.metadata.evidence_ids.join(", ") || "None"}
                  </td>
                  <td className="py-3 pr-3">
                    <FindingStatusBadge status={event.metadata.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm font-semibold text-neutral">No timeline events available.</p>
      )}
    </ReportSection>
  );
}

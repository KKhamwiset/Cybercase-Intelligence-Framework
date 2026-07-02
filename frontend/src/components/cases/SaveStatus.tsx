"use client";

export type SaveState = "idle" | "saving" | "saved" | "failed";

export default function SaveStatus({ state }: { state: SaveState }) {
  const text =
    state === "saving"
      ? "Saving"
      : state === "saved"
        ? "Saved"
        : state === "failed"
          ? "Save failed"
          : "Not saved";

  return (
    <span className="border border-black/15 bg-white px-3 py-2 text-xs font-black">
      {text}
    </span>
  );
}

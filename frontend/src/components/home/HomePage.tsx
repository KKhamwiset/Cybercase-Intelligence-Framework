import Link from "next/link";

const pillars: Array<{
  number: string;
  title: string;
  description: string;
  label: string;
  type: "bars" | "grid" | "line";
}> = [
  {
    number: "01",
    title: "Ask",
    description:
      "Bring an incident, question, or piece of evidence into one persistent conversation.",
    label: "Start anywhere",
    type: "bars",
  },
  {
    number: "02",
    title: "Clarify",
    description:
      "Work through missing context with focused, backend-managed follow-up questions.",
    label: "Guided context",
    type: "grid",
  },
  {
    number: "03",
    title: "Continue",
    description:
      "Keep saved chat threads available so every investigation can pick up where it left off.",
    label: "Saved threads",
    type: "line",
  },
];

function MiniVisual({ type }: { type: "bars" | "grid" | "line" }) {
  if (type === "bars") {
    return (
      <div className="space-y-3 pt-2">
        {[100, 78, 88, 56, 70].map((width, index) => (
          <div
            key={index}
            className="h-px bg-ivory/30"
            style={{ width: `${width}%` }}
          />
        ))}
      </div>
    );
  }

  if (type === "grid") {
    return (
      <div className="grid grid-cols-5 gap-2 pt-2">
        {Array.from({ length: 10 }).map((_, index) => (
          <div
            key={index}
            className={`aspect-square border ${
              index === 2 || index === 6
                ? "border-ivory bg-ivory"
                : "border-ivory/30"
            }`}
          />
        ))}
      </div>
    );
  }

  return (
    <svg
      viewBox="0 0 260 120"
      className="mt-2 h-28 w-full"
      role="img"
      aria-label="Threat trend"
    >
      <line x1="10" y1="102" x2="250" y2="102" stroke="rgba(255,255,255,.2)" />
      <polyline
        points="10,88 68,45 118,72 168,30 220,58 250,18"
        fill="none"
        stroke="var(--color-ivory)"
        strokeWidth="2"
      />
      {[
        ["10", "88"],
        ["68", "45"],
        ["118", "72"],
        ["168", "30"],
        ["220", "58"],
        ["250", "18"],
      ].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="3" fill="var(--color-ivory)" />
      ))}
    </svg>
  );
}

export default function HomePage() {
  return (
    <main className="min-h-screen bg-line-strong text-charcoal">
      <div className="mx-auto overflow-hidden bg-ivory shadow-2xl">
        {/* Navigation */}
        <header className="flex items-center justify-between border-b border-charcoal/10 px-5 py-4 md:px-8">
          <Link
            href="/"
            className="flex items-center gap-2 font-semibold tracking-tight"
          >
            <span className="grid h-6 w-6 place-items-center bg-charcoal text-xs font-black text-ivory">
              C
            </span>
            <span>CyberCase Framework</span>
          </Link>

          <nav className="hidden items-center gap-7 text-[11px] font-bold uppercase tracking-widest text-charcoal/60 md:flex">
            <a href="#platform" className="transition hover:text-charcoal">
              Platform
            </a>
            <a href="#workflow" className="transition hover:text-charcoal">
              Workflow
            </a>
            <a href="#intelligence" className="transition hover:text-charcoal">
              Intelligence
            </a>
            <a href="#about" className="transition hover:text-charcoal">
              About
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/chat"
              className="hidden text-[11px] font-bold uppercase tracking-wider text-charcoal/60 hover:text-charcoal sm:block"
            >
              Open chat
            </Link>

            <Link
              href="/chat"
              className="flex items-center gap-3 bg-charcoal px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-ivory transition hover:bg-charcoal-hover active:bg-charcoal-pressed"
            >
              Start case
              <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
            </Link>
          </div>
        </header>

        {/* Hero */}
        <section className="relative min-h-180 overflow-hidden px-5 pb-10 pt-20 md:min-h-205 md:px-10 md:pt-28">
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex h-[58%] items-end justify-center gap-0 opacity-80">
            <div className="h-[32%] w-[14%] border border-charcoal/10" />
            <div className="h-[48%] w-[14%] border border-charcoal/10" />
            <div className="h-[68%] w-[14%] border border-charcoal/10" />
            <div className="h-[94%] w-[14%] border border-charcoal/10" />
            <div className="h-[74%] w-[14%] border border-charcoal/10" />
            <div className="h-[90%] w-[14%] border border-charcoal/10" />
            <div className="h-[46%] w-[14%] border border-charcoal/10" />
          </div>

          <div className="relative z-10 mx-auto max-w-4xl text-center">
            <p className="text-[10px] font-bold uppercase tracking-widest text-charcoal/60">
              Cyber Threat Intelligence Framework
            </p>

            <h1 className="mt-7 text-5xl font-light leading-[0.94] tracking-normal sm:text-6xl md:text-8xl">
              Make every investigation
              <br />
              <span className="font-normal">clearer, faster,</span>
              <br />
              and defensible.
            </h1>

            <p className="mx-auto mt-8 max-w-xl text-sm leading-relaxed text-ink-secondary md:text-base">
              CyberCase turns fragmented incident details into a persistent
              conversation where you can ask questions, add evidence, and
              keep the reasoning in one place.
            </p>

            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Link
                href="/chat"
                className="bg-charcoal px-5 py-3 text-[11px] font-bold uppercase tracking-widest text-ivory transition hover:bg-charcoal-hover active:bg-charcoal-pressed"
              >
                Start a chat
              </Link>

              <a
                href="#platform"
                className="border border-charcoal px-5 py-3 text-[11px] font-bold uppercase tracking-widest transition hover:bg-charcoal hover:text-ivory active:bg-charcoal-pressed"
              >
                Explore platform
              </a>
            </div>
          </div>

          <div className="absolute bottom-7 left-5 z-10 max-w-52.5 md:bottom-10 md:left-10">
            <p className="text-[10px] font-bold uppercase tracking-widest text-charcoal/60">
              Evidence-led conversation
            </p>
            <p className="mt-2 text-xs leading-relaxed text-ink-secondary">
              Keep each conversation grounded in retrieved context and
              analyst-confirmed details.
            </p>
          </div>

          <div className="absolute bottom-7 right-5 z-10 text-right md:bottom-10 md:right-10">
            <p className="text-[10px] font-bold uppercase tracking-widest text-charcoal/60">
              Built for analysts
            </p>
            <p className="mt-2 text-xs text-ink-secondary">
              Persistent chat · Guided follow-up · Saved threads
            </p>
          </div>
        </section>

        {/* Dark Platform */}
        <section
          id="platform"
          className="bg-charcoal px-5 py-10 text-ivory md:px-10 md:py-16"
        >
          <div className="flex flex-col gap-6 border-b border-ivory/10 pb-8 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-ivory/60">
                CyberCase platform
              </p>
              <h2 className="mt-4 max-w-2xl text-4xl font-light leading-none tracking-normal md:text-6xl">
                From an open question
                <br />
                to a clear next step.
              </h2>
            </div>

            <p className="max-w-xs text-sm leading-relaxed text-ivory/70">
              A persistent workflow for asking, clarifying, and returning to
              every saved conversation.
            </p>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {pillars.map((pillar) => (
              <article
                key={pillar.number}
                className="group min-h-90 border border-ivory/15 bg-charcoal-pressed p-5 transition hover:-translate-y-1 hover:border-ivory/50"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-light text-ivory/70">
                    {pillar.number}
                  </span>
                  <span className="text-[10px] font-bold uppercase tracking-widest text-ivory/60">
                    {pillar.label}
                  </span>
                </div>

                <MiniVisual type={pillar.type} />

                <div className="mt-10">
                  <h3 className="text-3xl font-light tracking-normal">
                    {pillar.title}
                  </h3>
                  <p className="mt-4 max-w-xs text-sm leading-relaxed text-ivory/70">
                    {pillar.description}
                  </p>
                </div>

                <div className="mt-8 flex items-center justify-between border-t border-ivory/10 pt-4 text-[10px] font-bold uppercase tracking-widest text-ivory/65">
                  <span>Explore module</span>
                  <span className="text-red-500">↗</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* Workflow */}
        <section id="workflow" className="px-5 py-12 md:px-10 md:py-20">
          <div className="border border-charcoal bg-surface">
            <div className="flex items-center justify-between border-b border-charcoal px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-light text-red-600">01</span>
                <span className="text-xs font-bold uppercase tracking-widest">
                  Guided chat
                </span>
              </div>

              <Link
                href="/chat"
                className="border border-charcoal px-3 py-2 text-[10px] font-bold uppercase tracking-widest transition hover:bg-charcoal hover:text-ivory active:bg-charcoal-pressed"
              >
                Open chat
              </Link>
            </div>

            <div className="grid min-h-132.5 gap-10 px-6 py-16 md:grid-cols-[1.2fr_0.8fr] md:px-14">
              <div className="flex flex-col justify-center">
                <p className="text-[10px] font-bold uppercase tracking-widest text-charcoal/60">
                  Context first
                </p>

                <h2 className="mt-5 text-5xl font-light leading-[0.95] tracking-normal md:text-7xl">
                  Keep your
                  <br />
                  <span className="text-charcoal/25">context together.</span>
                </h2>

                <p className="mt-7 max-w-md text-sm leading-relaxed text-ink-secondary">
                  CyberCase keeps the context in one thread, asks focused
                  follow-up questions when something is missing, and lets you
                  return to saved conversations.
                </p>

                <Link
                  href="/chat"
                  className="mt-9 inline-flex w-fit items-center gap-3 bg-charcoal px-5 py-3 text-[11px] font-bold uppercase tracking-widest text-ivory transition hover:bg-charcoal-hover active:bg-charcoal-pressed"
                >
                  Start a conversation
                  <span className="text-red-500">●</span>
                </Link>
              </div>

              <div className="flex flex-col justify-end border-l border-charcoal/10 pl-6 md:pl-10">
                {[
                  [
                    "01",
                    "Start",
                    "Open a chat and describe what you need to understand.",
                  ],
                  [
                    "02",
                    "Clarify",
                    "Answer focused follow-ups when more context is needed.",
                  ],
                  [
                    "03",
                    "Continue",
                    "Keep each accepted message and response in the thread.",
                  ],
                  [
                    "04",
                    "Return",
                    "Come back to any saved chat without losing the thread.",
                  ],
                ].map(([number, title, description]) => (
                  <div
                    key={number}
                    className="border-t border-charcoal/15 py-5 first:border-t-0 first:pt-0"
                  >
                    <div className="flex gap-4">
                      <span className="text-xs font-bold text-red-600">
                        {number}
                      </span>
                      <div>
                        <h3 className="text-lg font-medium">{title}</h3>
                        <p className="mt-1 text-xs leading-relaxed text-ink-secondary">
                          {description}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Intelligence */}
        <section
          id="intelligence"
          className="grid border-t border-charcoal/10 md:grid-cols-2"
        >
          <div className="bg-charcoal px-6 py-14 text-ivory md:px-12 md:py-20">
            <p className="text-[10px] font-bold uppercase tracking-widest text-ivory/60">
              Intelligence layer
            </p>

            <h2 className="mt-5 text-4xl font-light leading-none tracking-normal md:text-6xl">
              Grounded answers,
              <br />
              not guesses.
            </h2>

            <p className="mt-7 max-w-md text-sm leading-relaxed text-ivory/70">
              Retrieval-Augmented Generation and persisted conversation context
              work together to keep answers traceable and useful.
            </p>
          </div>

          <div className="bg-surface-hover px-6 py-14 md:px-12 md:py-20">
            <div className="space-y-6">
              {[
                [
                  "Persistent context",
                  "Keep the accepted conversation available across sessions.",
                ],
                [
                  "Guided follow-up",
                  "Ask for the missing detail before continuing the analysis.",
                ],
                [
                  "Saved threads",
                  "Switch between multiple conversations from one workspace.",
                ],
                [
                  "Clear handoff",
                  "Keep questions, answers, and backend responses together.",
                ],
              ].map(([title, description], index) => (
                <article
                  key={title}
                  className="flex gap-5 border-b border-charcoal/15 pb-6 last:border-b-0"
                >
                  <span className="text-sm font-light text-red-600">
                    0{index + 1}
                  </span>
                  <div>
                    <h3 className="text-xl font-medium tracking-tight">
                      {title}
                    </h3>
                    <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-secondary">
                      {description}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer
          id="about"
          className="flex flex-col gap-5 border-t border-charcoal/10 px-5 py-7 text-xs text-ink-secondary md:flex-row md:items-center md:justify-between md:px-10"
        >
          <p>CyberCase Intelligence Framework</p>
          <div className="flex gap-5">
            <Link href="/chat" className="hover:text-charcoal">
              Workspace
            </Link>
            <a href="#platform" className="hover:text-charcoal">
              Platform
            </a>
          </div>
          <p>Built for evidence-led cyber conversations.</p>
        </footer>
      </div>
    </main>
  );
}

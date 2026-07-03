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
    title: "Investigate",
    description:
      "Turn scattered incident details, logs, and reports into a structured case context.",
    label: "Case intake",
    type: "bars",
  },
  {
    number: "02",
    title: "Map",
    description:
      "Connect observed behaviors with MITRE ATT&CK techniques and supporting evidence.",
    label: "Threat mapping",
    type: "grid",
  },
  {
    number: "03",
    title: "Report",
    description:
      "Generate analyst-ready reports with findings, gaps, evidence, and recommendations.",
    label: "Report generation",
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
            className="h-px bg-white/30"
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
                ? "border-white bg-white"
                : "border-white/30"
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
        stroke="white"
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
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="3" fill="white" />
      ))}
    </svg>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen bg-[#b7b7b7] text-black">
      <div className="mx-auto overflow-hidden bg-[#f4f4f2] shadow-2xl">
        {/* Navigation */}
        <header className="flex items-center justify-between border-b border-black/10 px-5 py-4 md:px-8">
          <Link
            href="/"
            className="flex items-center gap-2 font-semibold tracking-tight"
          >
            <span className="grid h-6 w-6 place-items-center bg-black text-xs font-black text-white">
              C
            </span>
            <span>CyberCase Framework</span>
          </Link>

          <nav className="hidden items-center gap-7 text-[11px] font-bold uppercase tracking-[0.16em] text-black/60 md:flex">
            <a href="#platform" className="transition hover:text-black">
              Platform
            </a>
            <a href="#workflow" className="transition hover:text-black">
              Workflow
            </a>
            <a href="#intelligence" className="transition hover:text-black">
              Intelligence
            </a>
            <a href="#about" className="transition hover:text-black">
              About
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/chat"
              className="hidden text-[11px] font-bold uppercase tracking-wider text-black/60 hover:text-black sm:block"
            >
              Open workspace
            </Link>

            <Link
              href="/chat"
              className="flex items-center gap-3 bg-black px-4 py-2 text-[10px] font-bold uppercase tracking-[0.15em] text-white transition hover:bg-black/80"
            >
              Start case
              <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
            </Link>
          </div>
        </header>

        {/* Hero */}
        <section className="relative min-h-[720px] overflow-hidden px-5 pb-10 pt-20 md:min-h-[820px] md:px-10 md:pt-28">
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex h-[58%] items-end justify-center gap-0 opacity-80">
            <div className="h-[32%] w-[14%] border border-black/10" />
            <div className="h-[48%] w-[14%] border border-black/10" />
            <div className="h-[68%] w-[14%] border border-black/10" />
            <div className="h-[94%] w-[14%] border border-black/10" />
            <div className="h-[74%] w-[14%] border border-black/10" />
            <div className="h-[90%] w-[14%] border border-black/10" />
            <div className="h-[46%] w-[14%] border border-black/10" />
          </div>

          <div className="relative z-10 mx-auto max-w-4xl text-center">
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-black/50">
              Cyber Threat Intelligence Framework
            </p>

            <h1 className="mt-7 text-5xl font-light leading-[0.94] tracking-[-0.06em] sm:text-6xl md:text-8xl">
              Make every case
              <br />
              <span className="font-normal">clearer, faster,</span>
              <br />
              and defensible.
            </h1>

            <p className="mx-auto mt-8 max-w-xl text-sm leading-relaxed text-black/55 md:text-base">
              CyberCase transforms fragmented incident data into structured
              intelligence, MITRE ATT&CK mappings, evidence gaps, and
              investigation-ready reports.
            </p>

            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Link
                href="/chat"
                className="bg-black px-5 py-3 text-[11px] font-bold uppercase tracking-[0.15em] text-white transition hover:bg-black/80"
              >
                Analyze a case
              </Link>

              <a
                href="#platform"
                className="border border-black px-5 py-3 text-[11px] font-bold uppercase tracking-[0.15em] transition hover:bg-black hover:text-white"
              >
                Explore platform
              </a>
            </div>
          </div>

          <div className="absolute bottom-7 left-5 z-10 max-w-[210px] md:bottom-10 md:left-10">
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-black/45">
              Evidence-led analysis
            </p>
            <p className="mt-2 text-xs leading-relaxed text-black/55">
              Ground every output in retrieved context, verified facts, and
              analyst-confirmed details.
            </p>
          </div>

          <div className="absolute bottom-7 right-5 z-10 text-right md:bottom-10 md:right-10">
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-black/45">
              Built for analysts
            </p>
            <p className="mt-2 text-xs text-black/55">
              RAG · Graph Intelligence · MITRE ATT&CK
            </p>
          </div>
        </section>

        {/* Dark Platform */}
        <section
          id="platform"
          className="bg-[#111111] px-5 py-10 text-white md:px-10 md:py-16"
        >
          <div className="flex flex-col gap-6 border-b border-white/10 pb-8 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/40">
                CyberCase platform
              </p>
              <h2 className="mt-4 max-w-2xl text-4xl font-light leading-none tracking-[-0.05em] md:text-6xl">
                From incident signals
                <br />
                to actionable intelligence.
              </h2>
            </div>

            <p className="max-w-xs text-sm leading-relaxed text-white/45">
              A structured workflow for threat investigation, evidence
              validation, MITRE mapping, and report generation.
            </p>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {pillars.map((pillar) => (
              <article
                key={pillar.number}
                className="group min-h-[360px] border border-white/15 bg-[#151515] p-5 transition hover:-translate-y-1 hover:border-white/50"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-light text-white/50">
                    {pillar.number}
                  </span>
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-white/35">
                    {pillar.label}
                  </span>
                </div>

                <MiniVisual type={pillar.type} />

                <div className="mt-10">
                  <h3 className="text-3xl font-light tracking-[-0.04em]">
                    {pillar.title}
                  </h3>
                  <p className="mt-4 max-w-xs text-sm leading-relaxed text-white/50">
                    {pillar.description}
                  </p>
                </div>

                <div className="mt-8 flex items-center justify-between border-t border-white/10 pt-4 text-[10px] font-bold uppercase tracking-[0.13em] text-white/45">
                  <span>Explore module</span>
                  <span className="text-red-500">↗</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* Workflow */}
        <section id="workflow" className="px-5 py-12 md:px-10 md:py-20">
          <div className="border border-black bg-[#f7f7f5]">
            <div className="flex items-center justify-between border-b border-black px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-light text-red-600">01</span>
                <span className="text-xs font-bold uppercase tracking-[0.14em]">
                  Guided investigation
                </span>
              </div>

              <Link
                href="/chat"
                className="border border-black px-3 py-2 text-[10px] font-bold uppercase tracking-[0.12em] transition hover:bg-black hover:text-white"
              >
                Open chat
              </Link>
            </div>

            <div className="grid min-h-[530px] gap-10 px-6 py-16 md:grid-cols-[1.2fr_0.8fr] md:px-14">
              <div className="flex flex-col justify-center">
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-black/40">
                  Context first
                </p>

                <h2 className="mt-5 text-5xl font-light leading-[0.95] tracking-[-0.06em] md:text-7xl">
                  Improve your
                  <br />
                  <span className="text-black/20">case confidence.</span>
                </h2>

                <p className="mt-7 max-w-md text-sm leading-relaxed text-black/55">
                  CyberCase identifies missing details early, asks precise
                  follow-up questions, and keeps the investigation grounded in
                  available evidence.
                </p>

                <Link
                  href="/chat"
                  className="mt-9 inline-flex w-fit items-center gap-3 bg-black px-5 py-3 text-[11px] font-bold uppercase tracking-[0.14em] text-white transition hover:bg-black/80"
                >
                  Start investigation
                  <span className="text-red-500">●</span>
                </Link>
              </div>

              <div className="flex flex-col justify-end border-l border-black/10 pl-6 md:pl-10">
                {[
                  [
                    "01",
                    "Collect",
                    "Capture incident facts, evidence, and observed indicators.",
                  ],
                  [
                    "02",
                    "Validate",
                    "Detect ambiguity and request the missing details.",
                  ],
                  [
                    "03",
                    "Connect",
                    "Map verified behavior to MITRE and related intelligence.",
                  ],
                  [
                    "04",
                    "Generate",
                    "Produce structured reports ready for analyst review.",
                  ],
                ].map(([number, title, description]) => (
                  <div
                    key={number}
                    className="border-t border-black/15 py-5 first:border-t-0 first:pt-0"
                  >
                    <div className="flex gap-4">
                      <span className="text-xs font-bold text-red-600">
                        {number}
                      </span>
                      <div>
                        <h3 className="text-lg font-medium">{title}</h3>
                        <p className="mt-1 text-xs leading-relaxed text-black/50">
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
          className="grid border-t border-black/10 md:grid-cols-2"
        >
          <div className="bg-black px-6 py-14 text-white md:px-12 md:py-20">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/40">
              Intelligence layer
            </p>

            <h2 className="mt-5 text-4xl font-light leading-none tracking-[-0.05em] md:text-6xl">
              Grounded outputs,
              <br />
              not guesses.
            </h2>

            <p className="mt-7 max-w-md text-sm leading-relaxed text-white/50">
              Retrieval-Augmented Generation, knowledge graphs, and
              analyst-confirmed facts work together to reduce hallucination and
              make findings traceable.
            </p>
          </div>

          <div className="bg-[#e8e8e5] px-6 py-14 md:px-12 md:py-20">
            <div className="space-y-6">
              {[
                [
                  "RAG Retrieval",
                  "Relevant laws, case documents, and CTI context.",
                ],
                [
                  "Graph Intelligence",
                  "Verified relationships between techniques, evidence, and standards.",
                ],
                [
                  "Gap Analysis",
                  "Targeted follow-ups when context is insufficient.",
                ],
                [
                  "Report Engine",
                  "Structured outputs for incident response and documentation.",
                ],
              ].map(([title, description], index) => (
                <article
                  key={title}
                  className="flex gap-5 border-b border-black/15 pb-6 last:border-b-0"
                >
                  <span className="text-sm font-light text-red-600">
                    0{index + 1}
                  </span>
                  <div>
                    <h3 className="text-xl font-medium tracking-tight">
                      {title}
                    </h3>
                    <p className="mt-2 max-w-md text-sm leading-relaxed text-black/55">
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
          className="flex flex-col gap-5 border-t border-black/10 px-5 py-7 text-xs text-black/45 md:flex-row md:items-center md:justify-between md:px-10"
        >
          <p>CyberCase Intelligence Framework</p>
          <div className="flex gap-5">
            <Link href="/chat" className="hover:text-black">
              Workspace
            </Link>
            <Link href="/report" className="hover:text-black">
              Reports
            </Link>
            <a href="#platform" className="hover:text-black">
              Platform
            </a>
          </div>
          <p>Built for evidence-led cyber investigations.</p>
        </footer>
      </div>
    </main>
  );
}

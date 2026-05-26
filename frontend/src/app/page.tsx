"use client";

import { useEffect, useState } from "react";
import { getHealthStatus } from "@/lib/api";
import Link from "next/link";

export default function Home() {
  const [dbStatus, setDbStatus] = useState<"loading" | "connected" | "error">(
    "loading",
  );

  useEffect(() => {
    async function checkHealth() {
      try {
        const status = await getHealthStatus();
        if (status.database === "connected") {
          setDbStatus("connected");
        } else {
          setDbStatus("error");
        }
      } catch {
        setDbStatus("error");
      }
    }
    checkHealth();
  }, []);

  return (
    <main className="relative min-h-screen flex flex-col bg-background">
      {/* Navigation */}
      <nav className="relative z-10 flex justify-between items-center px-6 lg:px-12 py-6 bg-white border-b border-gray-200">
        <div className="flex items-center gap-3 text-xl font-bold tracking-tight text-primary">
          <div className="w-8 h-8 bg-primary text-white rounded flex items-center justify-center text-sm">
            C
          </div>
          CyberCase Framework
        </div>
        <ul className="hidden md:flex gap-8 list-none">
          <li>
            <a
              href="#"
              className="text-neutral text-sm font-medium transition-colors hover:text-primary"
            >
              Documents
            </a>
          </li>
          <li>
            <Link
              href="/chat"
              className="text-neutral text-sm font-medium transition-colors hover:text-primary"
            >
              RAG Search
            </Link>
          </li>
          <li>
            <a
              href="#"
              className="text-neutral text-sm font-medium transition-colors hover:text-primary"
            >
              Settings
            </a>
          </li>
        </ul>
        <div className="hidden md:block">
          <Link href="/chat" className="btn-primary inline-block">
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative z-10 flex-1 flex flex-col justify-center items-center text-center px-6 lg:px-8 py-24 gap-8">
        <div className="bg-white border border-gray-200 shadow-sm inline-flex items-center gap-2 px-6 py-2 rounded-full text-xs font-medium text-secondary">
          <div
            className={`w-2 h-2 rounded-full ${
              dbStatus === "error"
                ? "bg-red-500"
                : dbStatus === "loading"
                  ? "bg-amber-500"
                  : "bg-emerald-500"
            }`}
          ></div>
          {dbStatus === "connected"
            ? "Systems Online & Database Connected"
            : dbStatus === "loading"
              ? "Connecting to Database..."
              : "Database Connection Failed"}
        </div>

        <h1 className="text-[clamp(2.5rem,6vw,4.5rem)] font-extrabold tracking-tight leading-[1.1] text-primary">
          Thai Law <br />
          <span className="text-secondary">Intelligent Platform</span>
        </h1>

        <p className="max-w-150 text-lg text-neutral leading-relaxed">
          Advanced Retrieval-Augmented Generation (RAG) platform specialized in
          Thai Cybersecurity, PDPA, and Electronic Transactions Acts.
        </p>

        <div className="flex gap-4 mt-4">
          <Link href="/chat" className="btn-primary inline-block">
            Start Search
          </Link>
          <button className="btn-outlined">View Documents</button>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 w-full max-w-225 mt-12">
          <div className="card p-8 text-left transition-shadow hover:shadow-md">
            <div className="w-10 h-10 bg-secondary text-white rounded-md flex items-center justify-center mb-6">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
            </div>
            <h3 className="text-lg font-bold mb-2 text-primary">
              Semantic Search
            </h3>
            <p className="text-sm text-neutral leading-relaxed">
              Find relevant legal clauses across multiple documents using
              advanced FAISS vector search.
            </p>
          </div>

          <div className="card p-8 text-left transition-shadow hover:shadow-md">
            <div className="w-10 h-10 bg-secondary text-white rounded-md flex items-center justify-center mb-6">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 8V4H8" />
                <rect width="16" height="12" x="4" y="8" rx="2" />
                <path d="M2 14h2" />
                <path d="M20 14h2" />
                <path d="M15 13v2" />
                <path d="M9 13v2" />
              </svg>
            </div>
            <h3 className="text-lg font-bold mb-2 text-primary">AI Analysis</h3>
            <p className="text-sm text-neutral leading-relaxed">
              Get precise answers with exact page citations generated by Claude
              3 Haiku.
            </p>
          </div>

          <div className="card p-8 text-left transition-shadow hover:shadow-md sm:col-span-2 lg:col-span-1">
            <div className="w-10 h-10 bg-secondary text-white rounded-md flex items-center justify-center mb-6">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="m13 2-2 2.5h3L11 22l2-2.5H10l3-17.5Z" />
              </svg>
            </div>
            <h3 className="text-lg font-bold mb-2 text-primary">
              Hybrid Retrieval
            </h3>
            <p className="text-sm text-neutral leading-relaxed">
              Combine dense vector embeddings with BM25 sparse keyword matching
              for optimal accuracy.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 text-center p-8 text-neutral text-xs border-t border-gray-200 mt-auto bg-white">
        &copy; {new Date().getFullYear()} CyberCase Framework. Built for Thai
        Legal Intelligence.
      </footer>
    </main>
  );
}

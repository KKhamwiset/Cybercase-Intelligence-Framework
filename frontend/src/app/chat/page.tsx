"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  chatContinue,
  ChatMessage,
  queryRagFile,
  resumeRag,
  QueryResponse,
} from "@/lib/api";
import Link from "next/link";
import FollowUpModule from "@/components/FollowUpModule";

/**
 * Chat Page Component
 * Provides a clean black and white interface for interacting with the RAG-powered chatbot.
 */
export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [followUpResponse, setFollowUpResponse] = useState<QueryResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom of the chat history
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && !selectedFile) || isLoading) return;

    const currentInput = input;
    const currentFile = selectedFile;
    const userMessage: ChatMessage = {
      role: "user",
      content: currentFile
        ? `${currentInput || "Analyze this document"}\n\nAttached file: ${currentFile.name}`
        : currentInput,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setIsLoading(true);

    try {
      let response: QueryResponse;
      if (currentSessionId) {
        response = await resumeRag(currentSessionId, currentInput);
      } else if (currentFile) {
        response = await queryRagFile(currentFile, currentInput);
      } else {
        response = await chatContinue(currentInput, messages);
      }

      if (response.status === "followup") {
        setCurrentSessionId(response.session_id || null);
        setFollowUpResponse(response);
      } else {
        setCurrentSessionId(null);
        setFollowUpResponse(null);
        const aiMessage: ChatMessage = {
          role: "assistant",
          content: response.answer,
        };
        setMessages((prev) => [...prev, aiMessage]);
      }
    } catch (error) {
      console.error("Chat error:", error);
      const errorMessage: ChatMessage = {
        role: "assistant",
        content:
          "ขออภัย เกิดข้อผิดพลาดในการประมวลผลคำขอของคุณ โปรดลองอีกครั้งในภายหลัง",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
  };

  return (
    <div className="flex flex-col h-screen bg-background font-sans">
      {/* Navigation Header */}
      <nav className="relative z-10 flex justify-between items-center px-6 lg:px-12 py-4 bg-white border-b border-gray-200 shadow-sm">
        <Link
          href="/"
          className="flex items-center gap-3 text-xl font-bold tracking-tight text-primary hover:opacity-80 transition-opacity"
        >
          <div className="w-8 h-8 bg-primary text-white rounded flex items-center justify-center text-sm">
            C
          </div>
          CyberCase Framework
        </Link>
        <div className="hidden md:flex items-center gap-6">
          <span className="text-xs font-medium text-neutral uppercase tracking-widest bg-gray-100 px-3 py-1 rounded-full">
            AI Assistant
          </span>
          <Link
            href="/"
            className="text-sm font-medium text-neutral hover:text-primary transition-colors"
          >
            Exit Chat
          </Link>
        </div>
      </nav>

      {/* Chat Messages Area */}
      <main className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center space-y-6">
              <div className="w-16 h-16 bg-primary text-white rounded-2xl flex items-center justify-center shadow-lg transform -rotate-3">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="32"
                  height="32"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z" />
                </svg>
              </div>
              <div className="space-y-2">
                <h2 className="text-3xl font-extrabold text-primary tracking-tight">
                  How can I help you today?
                </h2>
                <p className="text-neutral max-w-md mx-auto">
                  Ask me about Thai Cybersecurity law, PDPA, or technical
                  queries regarding MITRE ATT&CK.
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-lg mt-4">
                {["PDPA คืออะไร?", "อธิบายมาตรา 24 พรบ.คอม"].map((q) => (
                  <button
                    key={q}
                    onClick={() => {
                      setInput(q);
                    }}
                    className="text-sm text-left px-4 py-3 bg-white border border-gray-200 rounded-xl hover:border-primary hover:bg-gray-50 transition-all text-secondary font-medium shadow-sm"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, index) => (
            <div
              key={index}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-2 duration-300`}
            >
              <div
                className={`max-w-[85%] md:max-w-[75%] rounded-2xl px-5 py-4 ${
                  msg.role === "user"
                    ? "bg-primary text-white shadow-md rounded-br-none"
                    : "bg-white text-primary border border-gray-200 shadow-sm rounded-bl-none"
                }`}
              >
                <div className="text-[10px] font-bold uppercase tracking-tighter mb-1 opacity-50">
                  {msg.role === "user" ? "You" : "Assistant"}
                </div>
                <p className="whitespace-pre-wrap leading-relaxed text-sm md:text-base font-medium">
                  {msg.content}
                </p>
              </div>
            </div>
          ))}

          {followUpResponse && followUpResponse.status === "followup" && (
            <FollowUpModule
              question={followUpResponse.followup_question || "I need more information."}
              sessionId={followUpResponse.session_id || ""}
              onResolved={(response) => {
                setFollowUpResponse(null);
                setCurrentSessionId(null);
                const aiMessage: ChatMessage = {
                  role: "assistant",
                  content: response.answer,
                };
                setMessages((prev) => [...prev, aiMessage]);
              }}
              onError={(error) => {
                console.error("Follow-up error:", error);
                setFollowUpResponse(null);
              }}
            />
          )}

          {isLoading && (
            <div className="flex justify-start animate-pulse">
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-none px-5 py-4 shadow-sm">
                <div className="flex space-x-2 py-2">
                  <div
                    className="w-2 h-2 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-primary rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  ></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <footer className="bg-white border-t border-gray-200 p-4 md:p-8 sticky bottom-0">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex flex-col md:flex-row md:items-center gap-3 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3">
              <label className="flex flex-1 cursor-pointer items-center gap-3 text-sm font-medium text-primary">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-gray-200 bg-white">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
                    <path d="M14 2v4a2 2 0 0 0 2 2h4" />
                    <path d="M10 12H8" />
                    <path d="M16 16H8" />
                    <path d="M16 20H8" />
                  </svg>
                </span>
                <span className="min-w-0">
                  <span className="block truncate">
                    {selectedFile
                      ? selectedFile.name
                      : "Attach PDF or image for OCR"}
                  </span>
                  <span className="block text-xs font-normal text-neutral">
                    PDF, PNG, JPG, or JPEG
                  </span>
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                  onChange={handleFileChange}
                  disabled={isLoading}
                  className="sr-only"
                />
              </label>

              <div className="flex items-center gap-2">
                {selectedFile && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFile(null);
                      if (fileInputRef.current) {
                        fileInputRef.current.value = "";
                      }
                    }}
                    disabled={isLoading}
                    className="h-10 rounded-xl border border-gray-200 bg-white px-3 text-xs font-bold uppercase tracking-widest text-neutral transition-colors hover:text-primary disabled:opacity-50"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>

            <div className="relative flex items-center group">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  currentSessionId
                    ? "Answer the follow-up question..."
                    : selectedFile
                      ? "Ask what to analyze from this file..."
                      : "Ask anything about Thai regulations..."
                }
                disabled={isLoading}
                className={`w-full bg-gray-50 border ${currentSessionId ? "border-amber-300 ring-1 ring-amber-100" : "border-gray-200"} focus:border-primary focus:bg-white rounded-2xl py-5 pl-6 pr-16 text-primary outline-none transition-all disabled:opacity-50 shadow-sm group-hover:shadow-md`}
              />
              <button
                type="submit"
                disabled={isLoading || (!input.trim() && !selectedFile)}
                className="absolute right-3 p-3 bg-primary hover:bg-secondary text-white rounded-xl transition-all disabled:opacity-50 disabled:bg-neutral transform active:scale-95 shadow-sm"
                aria-label="Send message"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="m22 2-7 20-4-9-9-4Z" />
                  <path d="M22 2 11 13" />
                </svg>
              </button>
            </div>
          </form>
          <div className="flex justify-between items-center mt-4 px-2">
            <p className="text-[10px] text-neutral font-medium uppercase tracking-widest">
              CyberCase Framework &bull; Intelligence Engine
            </p>
            <p className="text-[10px] text-neutral font-medium">
              Thai Legal Intelligence RAG
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

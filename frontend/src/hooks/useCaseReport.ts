"use client";

import { useQuery } from "@tanstack/react-query";
import axios from "axios";

import { getCaseReport, ReportViewModel } from "@/lib/reports";

type UseCaseReportState = {
  report: ReportViewModel | null;
  isLoading: boolean;
  error: string;
  notFound: boolean;
};

export function useCaseReport(caseId: string | null): UseCaseReportState {
  const query = useQuery<ReportViewModel>({
    queryKey: caseId ? ["case-report", caseId] : ["case-report", "missing"],
    queryFn: ({ signal }) => {
      if (!caseId) {
        throw new Error("caseId is required");
      }
      return getCaseReport(caseId, signal);
    },
    enabled: Boolean(caseId),
    retry: (failureCount, error) => {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });

  if (!caseId) {
    return { report: null, isLoading: false, error: "", notFound: false };
  }

  const notFound = axios.isAxiosError(query.error) && query.error.response?.status === 404;
  return {
    report: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error && !notFound ? "Could not load the case report." : "",
    notFound,
  };
}

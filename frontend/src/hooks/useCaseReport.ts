"use client";

import { useQuery } from "@tanstack/react-query";
import axios from "axios";

import { getLatestCaseReport, type CyberCaseReport, type ReportCompletedResponse } from "@/lib/api";

type UseCaseReportState = {
  report: CyberCaseReport | null;
  isLoading: boolean;
  error: string;
  notFound: boolean;
};

export function useCaseReport(caseId: string | null): UseCaseReportState {
  const query = useQuery<ReportCompletedResponse>({
    queryKey: caseId ? ["case-report", caseId] : ["case-report", "missing"],
    queryFn: ({ signal }) => {
      if (!caseId) {
        throw new Error("caseId is required");
      }
      void signal;
      return getLatestCaseReport(caseId).then((response) => {
        if (response.status !== "completed") {
          throw new Error("The report is not completed");
        }
        return response;
      });
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
    report: query.data?.report ?? null,
    isLoading: query.isLoading,
    error: query.error && !notFound ? "Could not load the case report." : "",
    notFound,
  };
}

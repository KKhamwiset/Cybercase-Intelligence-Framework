"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import {
  CaseCreateInput,
  CaseUpdateInput,
  createCase,
  getCase,
  listCases,
  StructuredCase,
  updateCase,
} from "@/lib/cases";
import { caseAnalysisKeys } from "@/lib/case-chat";

export const caseKeys = {
  all: ["cases"] as const,
  lists: () => [...caseKeys.all, "list"] as const,
  detail: (caseId: string) => [...caseKeys.all, caseId] as const,
};

export function useCase(caseId: string | null) {
  return useQuery({
    queryKey: caseId ? caseKeys.detail(caseId) : [...caseKeys.all, "missing"],
    queryFn: ({ signal }) => {
      if (!caseId) {
        throw new Error("caseId is required");
      }
      return getCase(caseId, signal);
    },
    enabled: Boolean(caseId),
    retry: (failureCount, error) => {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });
}

export function useCases() {
  return useQuery({
    queryKey: caseKeys.lists(),
    queryFn: ({ signal }) => listCases(signal),
  });
}

export function useCreateCase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CaseCreateInput) => createCase(input),
    onSuccess: (createdCase) => {
      queryClient.setQueryData(caseKeys.detail(createdCase.case_id), createdCase);
      void queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
    },
  });
}

export function useUpdateCase(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CaseUpdateInput) => updateCase(caseId, input),
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: caseKeys.detail(caseId) });
      const previous = queryClient.getQueryData<StructuredCase>(caseKeys.detail(caseId));
      if (previous) {
        queryClient.setQueryData(caseKeys.detail(caseId), { ...previous, ...input });
      }
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) {
        queryClient.setQueryData(caseKeys.detail(caseId), context.previous);
      }
    },
    onSuccess: (savedCase) => {
      queryClient.setQueryData(caseKeys.detail(caseId), savedCase);
      void queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: caseAnalysisKeys.workspace(caseId) });
      void queryClient.invalidateQueries({ queryKey: caseAnalysisKeys.readiness(caseId) });
    },
  });
}

export function isNotFound(error: unknown) {
  return axios.isAxiosError(error) && error.response?.status === 404;
}

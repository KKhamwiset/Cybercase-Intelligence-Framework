"use client";

import { useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import {
  CaseCreateInput,
  CaseUpdateInput,
  createCase,
  deleteCase,
  getCase,
  getCaseOutputs,
  listCases,
  updateCase,
} from "@/lib/cases";
import { caseAnalysisKeys } from "@/lib/case-chat";

export const caseKeys = {
  all: ["cases"] as const,
  lists: () => [...caseKeys.all, "list"] as const,
  detail: (caseId: string) => [...caseKeys.all, caseId] as const,
  outputs: (caseId: string) => [...caseKeys.detail(caseId), "outputs"] as const,
};

export const caseMutationKeys = {
  item: (caseId: string) => ["case-mutation", caseId] as const,
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

export function useCaseOutputs(caseId: string | null) {
  return useQuery({
    queryKey: caseId ? caseKeys.outputs(caseId) : [...caseKeys.all, "missing", "outputs"],
    queryFn: ({ signal }) => {
      if (!caseId) {
        throw new Error("caseId is required");
      }
      return getCaseOutputs(caseId, signal);
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

export function useCaseActionPending(caseId: string): boolean {
  return useIsMutating({ mutationKey: caseMutationKeys.item(caseId) }) > 0;
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
    mutationKey: caseMutationKeys.item(caseId),
    mutationFn: (input: CaseUpdateInput) => updateCase(caseId, input),
    onSuccess: (savedCase) => {
      queryClient.setQueryData(caseKeys.detail(caseId), savedCase);
      queryClient.removeQueries({ queryKey: caseKeys.outputs(caseId), exact: true });
      void queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
      void queryClient.invalidateQueries({ queryKey: caseAnalysisKeys.workspace(caseId) });
      void queryClient.invalidateQueries({ queryKey: caseAnalysisKeys.readiness(caseId) });
      void queryClient.invalidateQueries({ queryKey: caseKeys.outputs(caseId) });
    },
  });
}

export function useDeleteCase(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: caseMutationKeys.item(caseId),
    mutationFn: () => deleteCase(caseId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: caseKeys.detail(caseId) });
      void queryClient.invalidateQueries({ queryKey: caseKeys.lists() });
    },
  });
}

export function isNotFound(error: unknown) {
  return axios.isAxiosError(error) && error.response?.status === 404;
}

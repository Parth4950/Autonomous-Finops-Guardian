import { useQuery } from "@tanstack/react-query";
import { fetchAnomalies } from "@/api/anomalies";
import { fetchAudit, fetchExecutiveReport } from "@/api/audit";
import { enrichResources } from "@/api/enrich";
import { fetchExecutions } from "@/api/executions";
import { fetchForecast } from "@/api/forecast";
import { fetchHealth } from "@/api/health";
import { fetchPlans } from "@/api/plans";
import { fetchApprovals } from "@/api/approvals";
import { fetchResources } from "@/api/resources";
import { fetchRisk } from "@/api/risk";
import { fetchWaste } from "@/api/waste";
import { queryKeys } from "@/hooks/queryKeys";

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: fetchHealth,
    staleTime: 30_000,
  });
}

export function useResources() {
  return useQuery({
    queryKey: queryKeys.resources,
    queryFn: fetchResources,
  });
}

export function useWaste() {
  return useQuery({
    queryKey: queryKeys.waste,
    queryFn: fetchWaste,
  });
}

export function useRisk() {
  return useQuery({
    queryKey: queryKeys.risk,
    queryFn: fetchRisk,
  });
}

export function useAudit() {
  return useQuery({
    queryKey: queryKeys.audit,
    queryFn: fetchAudit,
  });
}

export function useExecutiveReport() {
  return useQuery({
    queryKey: queryKeys.auditReport,
    queryFn: fetchExecutiveReport,
  });
}

export function usePlans() {
  return useQuery({
    queryKey: queryKeys.plans,
    queryFn: fetchPlans,
  });
}

export function useApprovals() {
  return useQuery({
    queryKey: queryKeys.approvals,
    queryFn: fetchApprovals,
  });
}

export function useExecutions() {
  return useQuery({
    queryKey: queryKeys.executions,
    queryFn: fetchExecutions,
  });
}

export function useAnomalies() {
  return useQuery({
    queryKey: queryKeys.anomalies,
    queryFn: fetchAnomalies,
  });
}

export function useForecast() {
  return useQuery({
    queryKey: queryKeys.forecast,
    queryFn: fetchForecast,
  });
}

export function useEnrichedResources() {
  return useQuery({
    queryKey: queryKeys.enrichedResources,
    queryFn: async () => {
      const [resources, waste, risk] = await Promise.all([
        fetchResources(),
        fetchWaste(),
        fetchRisk(),
      ]);
      return enrichResources(resources, waste, risk);
    },
  });
}

export function useOverview() {
  return useQuery({
    queryKey: queryKeys.overview,
    queryFn: async () => {
      const [resources, waste, risk, audit, approvals, executions] = await Promise.all([
        fetchResources(),
        fetchWaste(),
        fetchRisk(),
        fetchAudit(),
        fetchApprovals(),
        fetchExecutions(),
      ]);
      return { resources, waste, risk, audit, approvals, executions };
    },
  });
}

/** @deprecated Use useResources() */
export const useResourcesQuery = useResources;
/** @deprecated Use useWaste() */
export const useWasteQuery = useWaste;
/** @deprecated Use useRisk() */
export const useRiskQuery = useRisk;
/** @deprecated Use useAudit() */
export const useAuditQuery = useAudit;
/** @deprecated Use useExecutiveReport() */
export const useExecutiveReportQuery = useExecutiveReport;
/** @deprecated Use usePlans() */
export const usePlansQuery = usePlans;
/** @deprecated Use useApprovals() */
export const useApprovalsQuery = useApprovals;
/** @deprecated Use useExecutions() */
export const useExecutionsQuery = useExecutions;
/** @deprecated Use useEnrichedResources() */
export const useEnrichedResourcesQuery = useEnrichedResources;
/** @deprecated Use useOverview() */
export const useOverviewQuery = useOverview;

export { queryKeys };

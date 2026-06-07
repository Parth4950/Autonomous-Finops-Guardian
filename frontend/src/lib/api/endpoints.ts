/** @deprecated Import from `@/api/*` modules instead. */
export { fetchResources } from "@/api/resources";
export { fetchWaste as fetchWasteScores } from "@/api/waste";
export { fetchRisk as fetchRiskAssessments } from "@/api/risk";
export { fetchAudit as fetchAuditResults, fetchExecutiveReport } from "@/api/audit";
export { fetchPlans as fetchRemediationPlans } from "@/api/plans";
export { fetchApprovals, approveRemediation, rejectRemediation } from "@/api/approvals";
export { fetchExecutions } from "@/api/executions";
export { enrichResources } from "@/api/enrich";

import type {
  EnrichedResource,
  ResourceItem,
  RiskAssessmentItem,
  WasteScoreItem,
} from "@/api/types";

export function enrichResources(
  resources: ResourceItem[],
  waste: WasteScoreItem[],
  risk: RiskAssessmentItem[]
): EnrichedResource[] {
  const wasteMap = new Map(waste.map((item) => [item.resource_id, item]));
  const riskMap = new Map(risk.map((item) => [item.resource_id, item]));

  return resources.map((resource) => {
    const wasteItem = wasteMap.get(resource.resource_id);
    const riskItem = riskMap.get(resource.resource_id);

    return {
      ...resource,
      waste_score: wasteItem?.waste_score ?? null,
      waste_probability: wasteItem?.waste_probability ?? null,
      risk_score: riskItem?.risk_score ?? null,
      risk_level: riskItem?.risk_level ?? null,
      environment: riskItem?.environment ?? null,
    };
  });
}

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ExecutiveReport } from "@/lib/api/types";
import { Sparkles } from "lucide-react";

interface ExecutiveSummaryCardProps {
  report: ExecutiveReport | null;
  fallbackSummary: string;
}

export function ExecutiveSummaryCard({ report, fallbackSummary }: ExecutiveSummaryCardProps) {
  const summary = report?.executive_summary ?? fallbackSummary;

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-card via-card to-primary/5">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-primary" />
            Executive Summary
          </CardTitle>
          {report && (
            <Badge variant="outline" className="text-xs capitalize">
              {report.source === "gemini" ? "Gemini generated" : "Auditor report"}
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          AI-synthesized findings for FinOps leadership review
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm leading-relaxed text-foreground">{summary}</p>

        {report && (
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Key Findings
              </p>
              <ul className="space-y-1.5 text-sm text-muted-foreground">
                {report.key_findings.map((finding) => (
                  <li key={finding} className="flex gap-2">
                    <span className="text-primary">•</span>
                    <span>{finding}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Recommended Actions
              </p>
              <ul className="space-y-1.5 text-sm text-muted-foreground">
                {report.recommended_actions.map((action) => (
                  <li key={action} className="flex gap-2">
                    <span className="text-emerald-400">→</span>
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

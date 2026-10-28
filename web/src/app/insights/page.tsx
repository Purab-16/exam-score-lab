import type { Metadata } from "next";

import { PageTitle } from "@/components/api-state";
import { InsightsDashboard } from "@/components/insights/charts";

export const metadata: Metadata = { title: "Insights" };

export default function InsightsPage() {
  return (
    <>
      <PageTitle eyebrow="Dataset" title="What the data says about study habits">
        Patterns across all 1,000 students the model learned from. Hover any chart for exact numbers.
      </PageTitle>
      <InsightsDashboard />
    </>
  );
}

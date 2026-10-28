import type { Metadata } from "next";

import { PageTitle } from "@/components/api-state";
import { BatchUpload } from "@/components/batch/batch-upload";

export const metadata: Metadata = { title: "Batch prediction" };

export default function BatchPage() {
  return (
    <>
      <PageTitle eyebrow="Whole class" title="Predict scores for a whole class">
        Upload a CSV with one row per student. Rows are checked before predicting, and you can download the results.
      </PageTitle>
      <BatchUpload />
    </>
  );
}

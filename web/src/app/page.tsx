import { PageTitle } from "@/components/api-state";
import { Predictor } from "@/components/predictor/predictor";

export default function Home() {
  return (
    <>
      <PageTitle eyebrow="Single student" title="How will this student do in the final exam?">
        Describe the student&apos;s habits in four short steps. You get a predicted score, a likely range, and the
        changes that would help most.
      </PageTitle>
      <Predictor />
    </>
  );
}

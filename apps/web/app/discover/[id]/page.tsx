import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { PageContainer } from "@/components/layout/PageContainer";
import { ExperienceDetail } from "@/components/experience/ExperienceDetail";
import { getExperience } from "@/lib/api/experiences";
import { mapApiExperienceToUi } from "@/lib/api/experienceAdapter";
import { ApiError } from "@/lib/api/client";

async function fetchExperience(id: string) {
  try {
    const api = await getExperience(id);
    return mapApiExperienceToUi(api);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function generateMetadata({
  params,
}: PageProps<"/discover/[id]">): Promise<Metadata> {
  const { id } = await params;
  const experience = await fetchExperience(id).catch(() => null);
  return { title: experience?.title ?? "Experience" };
}

export default async function ExperienceDetailPage({
  params,
}: PageProps<"/discover/[id]">) {
  const { id } = await params;
  const experience = await fetchExperience(id);
  if (!experience) notFound();

  return (
    <PageContainer className="max-w-6xl py-8 sm:py-10">
      <ExperienceDetail experience={experience} />
    </PageContainer>
  );
}
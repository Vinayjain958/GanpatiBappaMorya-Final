"use client";

import { use } from "react";
import { EditExperienceClient } from "./EditExperienceClient";

export default function EditExperiencePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <EditExperienceClient experienceId={id} />;
}

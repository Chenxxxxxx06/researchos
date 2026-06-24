'use client';

import { use } from 'react';

import { SkillBuilder } from '@/features/skills/SkillBuilder';

export default function SkillBuilderPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  return <SkillBuilder projectId={projectId} />;
}

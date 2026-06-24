'use client';

import { use } from 'react';

import { SkillsMarketplace } from '@/features/skills/SkillsMarketplace';

export default function SkillsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  return <SkillsMarketplace projectId={projectId} />;
}

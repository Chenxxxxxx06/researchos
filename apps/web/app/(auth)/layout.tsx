'use client';

import { BookOpenCheck, Braces, FileCheck2, FlaskConical } from 'lucide-react';
import type { ReactNode } from 'react';

import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';
import { ThemeToggle } from '@/features/workspace/ThemeToggle';
import { useI18n } from '@/lib/i18n';

const STEPS = [
  { icon: BookOpenCheck, zh: '建立可引用的文献证据', en: 'Build citable literature evidence' },
  { icon: Braces, zh: '审查 Agent 代码补丁', en: 'Review every agent code patch' },
  { icon: FlaskConical, zh: '追踪实验、指标与版本', en: 'Trace experiments, metrics, and versions' },
  { icon: FileCheck2, zh: '让论文主张回到原始结果', en: 'Bind paper claims to source results' },
];

export default function AuthLayout({ children }: { children: ReactNode }) {
  const { locale, t } = useI18n();
  const zh = locale === 'zh-CN';

  return (
    <main className="grid min-h-[100dvh] bg-bg lg:grid-cols-[minmax(30rem,1.05fr)_minmax(28rem,0.95fr)]">
      <section className="mission-grid relative hidden overflow-hidden border-r border-border p-10 lg:flex lg:flex-col xl:p-14">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-md bg-accent text-base font-bold text-accent-fg shadow-elev1">R</span>
          <div>
            <h1 className="text-sm font-semibold tracking-[-0.02em] text-text">{t('app.name')}</h1>
            <p className="text-xs text-muted">Evidence-first research workspace</p>
          </div>
        </div>

        <div className="my-auto max-w-2xl py-12">
          <p className="text-xs font-medium text-accent">{zh ? '从研究问题到可核验成果' : 'From research question to verifiable output'}</p>
          <h2 className="mt-4 text-balance text-4xl font-semibold leading-[1.08] tracking-[-0.055em] text-text xl:text-5xl">
            {zh ? '把科研过程变成一条可以检查的证据链。' : 'Turn research into an evidence chain you can inspect.'}
          </h2>
          <p className="mt-5 max-w-xl text-base leading-7 text-muted">
            {zh ? '文献、代码、实验与论文不再散落在不同工具中。每一步保留来源、版本和人工决策。' : 'Keep literature, code, experiments, and writing connected through sources, versions, and human decisions.'}
          </p>

          <div className="mt-10 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2">
            {STEPS.map((step) => {
              const Icon = step.icon;
              return (
                <div key={step.en} className="flex min-h-28 flex-col justify-between bg-surface/88 p-4 backdrop-blur">
                  <Icon className="h-4 w-4 text-accent" aria-hidden="true" />
                  <p className="mt-6 text-sm font-medium leading-5 text-text">{zh ? step.zh : step.en}</p>
                </div>
              );
            })}
          </div>
        </div>

        <p className="text-xs leading-5 text-muted">
          {zh ? '危险操作始终需要确认。系统不会虚构文献、指标或实验结果。' : 'Risky actions always require approval. Sources, metrics, and results are never invented.'}
        </p>
      </section>

      <section className="relative flex min-h-[100dvh] items-center justify-center px-5 py-16 sm:px-8">
        <div className="absolute right-4 top-4 flex items-center gap-1.5 sm:right-6 sm:top-6">
          <ThemeToggle />
          <LanguageSwitcher />
        </div>
        <div className="w-full max-w-md">
          <div className="mb-7 lg:hidden">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-md bg-accent font-bold text-accent-fg">R</span>
              <div><h1 className="text-xl font-semibold tracking-[-0.03em] text-text">{t('app.name')}</h1><p className="text-xs text-muted">{t('app.tagline')}</p></div>
            </div>
          </div>
          {children}
        </div>
      </section>
    </main>
  );
}

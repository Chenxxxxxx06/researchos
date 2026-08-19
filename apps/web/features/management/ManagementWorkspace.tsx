'use client';

import { useQuery } from '@tanstack/react-query';
import {
  BookOpen,
  Building2,
  ExternalLink,
  FileText,
  FlaskConical,
  FolderKanban,
  Route,
  Settings2,
  StickyNote,
  Users,
} from 'lucide-react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { getManagementSummary } from '@/lib/api/management';
import { useI18n } from '@/lib/i18n';

import { SettingsPanel } from './SettingsPanel';

type Tab = 'researchers' | 'papers' | 'plans' | 'notes' | 'settings';

export function ManagementWorkspace({ projectId }: { projectId: string }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const searchParams = useSearchParams();
  const initialTab = useMemo<Tab>(() => {
    const requested = searchParams.get('tab');
    return isTab(requested) ? requested : 'researchers';
  }, [searchParams]);
  const [tab, setTab] = useState<Tab>(initialTab);
  const summary = useQuery({
    queryKey: ['management-summary', projectId],
    queryFn: () => getManagementSummary(projectId),
  });

  if (summary.isLoading) return <Skeleton className="h-[34rem] w-full" />;
  if (!summary.data) {
    return <div className="border border-danger/20 bg-danger-bg p-5 text-sm text-danger">{summary.error instanceof Error ? summary.error.message : 'Could not load management data.'}</div>;
  }

  const data = summary.data;
  const tabs: Array<{ id: Tab; label: string; count?: number; icon: typeof Users }> = [
    { id: 'researchers', label: zh ? '研究人员' : 'Researchers', count: data.counts.researchers, icon: Users },
    { id: 'papers', label: zh ? '文献资产' : 'Papers', count: data.counts.papers, icon: BookOpen },
    { id: 'plans', label: zh ? '实验方案' : 'Experiment plans', count: data.counts.experiment_plans, icon: FlaskConical },
    { id: 'notes', label: zh ? '阅读笔记' : 'Reading notes', count: data.counts.reading_notes, icon: StickyNote },
    { id: 'settings', label: zh ? '系统与模型' : 'System & models', icon: Settings2 },
  ];

  return (
    <div className="-m-5 min-h-[calc(100dvh-4rem)] bg-bg lg:-m-6 xl:-m-8">
      <header className="mission-grid border-b border-border bg-surface px-6 py-7 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <Badge variant="neutral" size="sm">CONTROL CENTER</Badge>
            <h1 className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-text">
              {zh ? '管理中心' : 'Management center'}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              {zh
                ? '在一个入口管理课题组成员、科研资产、界面偏好与模型连接。表格数据均来自后端持久化对象。'
                : 'Manage members, research assets, interface preferences, and model connections in one place. Every table is backed by persisted data.'}
            </p>
          </div>
          <div className="grid min-w-[22rem] grid-cols-2 gap-3">
            <IdentityCard icon={Building2} label={zh ? '课题组 / 组织' : 'Lab / organization'} title={data.organization.name} detail={`${data.organization.slug} · ${data.organization.plan}`} />
            <IdentityCard icon={FolderKanban} label={zh ? '当前项目' : 'Current project'} title={data.project.name} detail={`${data.project.field ?? (zh ? '未设置领域' : 'No field')} · ${data.project.status}`} />
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-x-8 gap-y-3 border-l-2 border-accent pl-5">
          <Metric icon={Route} label={zh ? '科研任务' : 'Missions'} value={data.counts.missions} />
          <Metric icon={Users} label={zh ? '研究人员' : 'Researchers'} value={data.counts.researchers} />
          <Metric icon={BookOpen} label={zh ? '文献' : 'Papers'} value={data.counts.papers} />
          <Metric icon={FlaskConical} label={zh ? '实验方案' : 'Plans'} value={data.counts.experiment_plans} />
          <Metric icon={StickyNote} label={zh ? '笔记' : 'Notes'} value={data.counts.reading_notes} />
        </div>
      </header>

      <div className="p-6 lg:p-8">
        <nav className="mb-6 flex max-w-full gap-1 overflow-x-auto border-b border-border" aria-label={zh ? '管理分类' : 'Management sections'}>
          {tabs.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`flex shrink-0 items-center gap-2 border-b-2 px-4 py-3 text-xs font-medium ${tab === item.id ? 'border-accent text-text' : 'border-transparent text-muted hover:text-text'}`}
              >
                <Icon className="h-3.5 w-3.5" />
                {item.label}
                {item.count !== undefined && <span className="bg-surface-2 px-1.5 py-0.5 font-mono text-[9px]">{item.count}</span>}
              </button>
            );
          })}
        </nav>

        {tab === 'settings' ? <SettingsPanel projectId={projectId} /> : (
          <section className="overflow-x-auto border border-border bg-surface shadow-sm">
            {tab === 'researchers' && (
              <table className="w-full min-w-[44rem] text-left text-xs">
                <Head values={[zh ? '人员' : 'Researcher', 'Email', zh ? '项目角色' : 'Project role', zh ? '状态' : 'Status']} />
                <tbody>{data.researchers.map((item) => <tr key={item.membership_id} className="border-t border-border hover:bg-surface-2/50"><Cell><p className="font-medium text-text">{item.display_name}</p></Cell><Cell>{item.email}</Cell><Cell><Badge size="sm" variant="info">{item.role}</Badge></Cell><Cell><Badge size="sm" variant={item.is_active ? 'success' : 'warn'}>{item.is_active ? (zh ? '有效' : 'Active') : (zh ? '停用' : 'Disabled')}</Badge></Cell></tr>)}</tbody>
              </table>
            )}
            {tab === 'papers' && (
              <table className="w-full min-w-[48rem] text-left text-xs">
                <Head values={[zh ? '文献' : 'Paper', zh ? '来源' : 'Source', zh ? '年份' : 'Year', zh ? '解析状态' : 'Ingest', '']} />
                <tbody>{data.papers.map((item) => <tr key={item.id} className="border-t border-border hover:bg-surface-2/50"><Cell><p className="max-w-2xl font-medium text-text">{item.title}</p><p className="mt-1 font-mono text-[9px] text-faint">{item.doi ?? item.id}</p></Cell><Cell>{item.source}</Cell><Cell>{item.year ?? '—'}</Cell><Cell><Badge size="sm" variant={item.ingest_status === 'completed' ? 'success' : 'neutral'}>{item.ingest_status}</Badge></Cell><Cell><Link aria-label={zh ? '打开文献' : 'Open paper'} href={`/projects/${projectId}/research/read/${item.id}`} className="text-info hover:underline"><ExternalLink className="h-3.5 w-3.5" /></Link></Cell></tr>)}</tbody>
              </table>
            )}
            {tab === 'plans' && (
              <table className="w-full min-w-[46rem] text-left text-xs">
                <Head values={[zh ? '方案' : 'Plan', zh ? '关联任务' : 'Mission', zh ? '状态' : 'Status', zh ? '版本' : 'Version', '']} />
                <tbody>{data.experiment_plans.map((item) => <tr key={item.id} className="border-t border-border hover:bg-surface-2/50"><Cell><p className="font-medium text-text">{item.title}</p></Cell><Cell>{item.mission_topic}</Cell><Cell><Badge size="sm" variant={item.status === 'published' ? 'success' : 'info'}>{item.status}</Badge></Cell><Cell>v{item.version}</Cell><Cell><Link aria-label={zh ? '打开实验方案' : 'Open plan'} href={`/projects/${projectId}/missions/${item.mission_id}/experiment-plan`} className="text-info hover:underline"><ExternalLink className="h-3.5 w-3.5" /></Link></Cell></tr>)}</tbody>
              </table>
            )}
            {tab === 'notes' && (
              <table className="w-full min-w-[46rem] text-left text-xs">
                <Head values={[zh ? '笔记' : 'Note', zh ? '论文' : 'Paper', zh ? '类型' : 'Type', zh ? '更新时间' : 'Updated', '']} />
                <tbody>{data.reading_notes.map((item) => <tr key={item.id} className="border-t border-border hover:bg-surface-2/50"><Cell><p className="max-w-xl line-clamp-2 text-text">{item.content}</p></Cell><Cell><p className="max-w-xs line-clamp-2">{item.paper_title}</p></Cell><Cell><Badge size="sm" variant="neutral">{item.note_type}</Badge></Cell><Cell>{new Date(item.updated_at).toLocaleDateString()}</Cell><Cell><Link aria-label={zh ? '打开阅读笔记' : 'Open note'} href={`/projects/${projectId}/research/read/${item.paper_id}${item.mission_id ? `?mission=${item.mission_id}` : ''}`} className="text-info hover:underline"><ExternalLink className="h-3.5 w-3.5" /></Link></Cell></tr>)}</tbody>
              </table>
            )}
          </section>
        )}

        {tab !== 'settings' && (
          <p className="mt-4 flex items-center gap-2 text-[10px] text-faint">
            <FileText className="h-3.5 w-3.5" />
            {zh ? '所有条目来自真实持久化对象；编辑入口继续沿用对应工作区的权限与审计规则。' : 'Every row is a persisted object; editors retain their workspace permissions and audit rules.'}
          </p>
        )}
      </div>
    </div>
  );
}

function isTab(value: string | null): value is Tab {
  return value === 'researchers' || value === 'papers' || value === 'plans' || value === 'notes' || value === 'settings';
}

function IdentityCard({ icon: Icon, label, title, detail }: { icon: typeof Building2; label: string; title: string; detail: string }) {
  return <div className="border-l-2 border-border-strong bg-surface/80 p-4"><div className="flex items-center gap-2 text-[10px] text-faint"><Icon className="h-3.5 w-3.5" />{label}</div><p className="mt-2 truncate text-sm font-semibold text-text">{title}</p><p className="mt-1 truncate text-[10px] text-muted">{detail}</p></div>;
}

function Metric({ icon: Icon, label, value }: { icon: typeof Route; label: string; value: number }) {
  return <div className="flex items-center gap-2"><Icon className="h-4 w-4 text-muted" /><div><p className="font-mono text-lg font-semibold text-text">{value}</p><p className="text-[9px] text-muted">{label}</p></div></div>;
}

function Head({ values }: { values: string[] }) {
  return <thead className="bg-surface-2"><tr>{values.map((value, index) => <th key={`${value}-${index}`} className="px-4 py-3 text-[10px] font-semibold tracking-wide text-muted">{value}</th>)}</tr></thead>;
}

function Cell({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 text-muted">{children}</td>;
}

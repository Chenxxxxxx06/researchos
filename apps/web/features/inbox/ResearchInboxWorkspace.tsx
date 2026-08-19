'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ClipboardList,
  FileAudio,
  FileText,
  Inbox,
  Loader2,
  MessageSquareText,
  Mic2,
  Upload,
  WandSparkles,
} from 'lucide-react';
import { useState } from 'react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getAgentRun } from '@/lib/api/agents';
import {
  analyzeInboxItem,
  createInboxItem,
  listInboxItems,
  uploadInboxFile,
  type InboxItem,
  type InboxSourceType,
} from '@/lib/api/inbox';
import { listLLMConfigs } from '@/lib/api/llmConfig';

import { StreamingVoiceCapture } from './StreamingVoiceCapture';

export function ResearchInboxWorkspace({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const items = useQuery({
    queryKey: ['research-inbox', projectId],
    queryFn: () => listInboxItems(projectId),
  });
  const configs = useQuery({ queryKey: ['llm-configs', projectId], queryFn: () => listLLMConfigs(projectId) });
  const analysisReady = Boolean(configs.data?.some((config) => config.is_active));
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [analysisMode, setAnalysisMode] = useState<
    'direction' | 'meeting_summary' | 'audio_to_paper'
  >('direction');
  const [form, setForm] = useState({
    source_type: 'message' as InboxSourceType,
    sender: '',
    title: '',
    content_text: '',
    original_filename: '',
    media_type: '',
  });
  const [fileHint, setFileHint] = useState('');

  const create = useMutation({
    mutationFn: async () => {
      if (selectedFile) {
        return uploadInboxFile(projectId, {
          file: selectedFile,
          sender: form.sender,
          title: form.title,
          analysis_mode: analysisMode,
          auto_analyze: analysisReady,
        });
      }
      const item = await createInboxItem(projectId, {
        ...form,
        sender: form.sender || null,
        original_filename: form.original_filename || null,
        media_type: form.media_type || null,
      });
      const analysis = analysisReady ? await analyzeInboxItem(projectId, item.id, analysisMode) : null;
      return { item, analysis };
    },
    onSuccess: () => {
      setForm({
        source_type: 'message',
        sender: '',
        title: '',
        content_text: '',
        original_filename: '',
        media_type: '',
      });
      setSelectedFile(null);
      setFileHint('');
      void queryClient.invalidateQueries({ queryKey: ['research-inbox', projectId] });
    },
  });

  return (
    <div className="-m-6 min-h-[calc(100vh-3rem)] bg-bg">
      <header className="border-b border-border bg-surface px-6 py-4">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-text">
          <Inbox className="h-5 w-5" /> Research Inbox
        </h1>
        <p className="mt-1 text-sm text-muted">
          收集导师、师兄和合作者的消息或转写稿，让 AI 提取方向、约束、待办与实验线索。
        </p>
      </header>

      <div className="grid gap-3 px-6 pt-6 md:grid-cols-3">
        <WorkflowCard
          icon={WandSparkles}
          title="方向提取"
          text="从消息中提取研究目标、约束、文献线索与实验待办。"
        />
        <WorkflowCard
          icon={ClipboardList}
          title="会议总结"
          text="生成决定、Action Items、负责人、依赖、分歧和下次会议材料。"
        />
        <WorkflowCard
          icon={Mic2}
          title="语音转论文"
          text="从录音转写稿生成论文蓝图与带 NEEDS EVIDENCE 标记的初稿。"
        />
      </div>

      <div className="grid gap-6 p-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>新增科研输入</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                create.mutate();
              }}
            >
              <div>
                <Label>类型</Label>
                <select
                  value={form.source_type}
                  onChange={(event) =>
                    setForm({ ...form, source_type: event.target.value as InboxSourceType })
                  }
                  className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text"
                >
                  <option value="message">聊天消息</option>
                  <option value="note">会议笔记</option>
                  <option value="file">文本文件</option>
                  <option value="audio_transcript">录音转写稿</option>
                </select>
              </div>
              <div>
                <Label>发送者</Label>
                <Input
                  value={form.sender}
                  onChange={(event) => setForm({ ...form, sender: event.target.value })}
                  placeholder="导师 / 师兄 / 合作者"
                />
              </div>
              <div>
                <Label>标题</Label>
                <Input
                  required
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                  placeholder="例如：组会后的实验调整"
                />
              </div>
              <div>
                <Label>消息、笔记或转写文本</Label>
                <div className="mb-2 mt-1.5">
                  <StreamingVoiceCapture
                    value={form.content_text}
                    onChange={(content_text) => setForm({
                      ...form,
                      source_type: 'audio_transcript',
                      content_text,
                      media_type: 'text/x-live-transcript',
                    })}
                  />
                </div>
                <textarea
                  value={form.content_text}
                  onChange={(event) => setForm({ ...form, content_text: event.target.value })}
                  className="min-h-44 w-full resize-y rounded-md border border-border-strong bg-surface p-3 text-sm text-text outline-none focus:ring-2 focus:ring-focus/60"
                  placeholder={selectedFile ? '文件将在服务端提取；这里可留空。' : '粘贴原始内容，系统会保留原文并单独生成 AI 总结。'}
                />
              </div>
              <div>
                <Label>自动分析方式</Label>
                <select
                  value={analysisMode}
                  onChange={(event) => setAnalysisMode(event.target.value as typeof analysisMode)}
                  className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text"
                >
                  <option value="direction">提取研究方向与行动清单</option>
                  <option value="meeting_summary">生成可追踪会议纪要</option>
                  <option value="audio_to_paper">生成论文蓝图与证据缺口</option>
                </select>
              </div>
              <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-border-strong p-3 text-xs text-muted hover:bg-surface-2">
                <Upload className="h-4 w-4" />
                {selectedFile ? selectedFile.name : '导入 PDF、DOCX、文本或录音'}
                <input
                  type="file"
                  className="sr-only"
                  accept=".txt,.md,.markdown,.csv,.json,.yaml,.yml,.log,.tex,.html,.htm,.pdf,.docx,audio/*"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    const isAudio = file.type.startsWith('audio/');
                    setSelectedFile(file);
                    setForm({
                      ...form,
                      source_type: isAudio ? 'audio_transcript' : 'file',
                      title: form.title || file.name,
                      original_filename: file.name,
                      media_type: file.type || 'application/octet-stream',
                    });
                    if (isAudio) setAnalysisMode('audio_to_paper');
                    setFileHint(`已选择 ${file.name}，保存后由服务端提取并立即分析。`);
                  }}
                />
              </label>
              {fileHint && <p className="text-xs text-muted">{fileHint}</p>}
              {!analysisReady && !configs.isLoading && <p className="border border-warn/25 bg-warn-bg p-3 text-[10px] leading-4 text-warn">文件和原文仍会真实提取、保存；Agent 总结暂不启动，避免 Mock 输出冒充分析。请先在<Link href={`/projects/${projectId}/manage?tab=settings`} className="mx-1 font-semibold underline">管理中心</Link>配置模型。音频文件还需要名为 <span className="font-mono">asr</span> 的转写配置。</p>}
              {create.error && (
                <p className="rounded-md bg-danger-bg p-2 text-xs text-danger">
                  {create.error instanceof Error ? create.error.message : '保存失败'}
                </p>
              )}
              <Button
                type="submit"
                className="w-full"
                loading={create.isPending}
                disabled={!form.title.trim() || (!form.content_text.trim() && !selectedFile)}
              >
                {analysisReady ? (selectedFile ? '上传、提取并分析' : '保存并开始分析') : (selectedFile ? '上传并提取原文' : '保存原文')}
              </Button>
            </form>
          </CardContent>
        </Card>

        <section className="space-y-4">
          {items.isLoading && <p className="text-sm text-muted">正在加载…</p>}
          {items.data?.length === 0 && (
            <div className="rounded-xl border border-dashed border-border p-12 text-center text-sm text-muted">
              暂无内容。先把一条导师消息或会议记录放进来。
            </div>
          )}
          {items.data?.map((item) => (
            <InboxItemCard key={item.id} projectId={projectId} item={item} analysisReady={analysisReady} />
          ))}
        </section>
      </div>
    </div>
  );
}

function InboxItemCard({ projectId, item, analysisReady }: { projectId: string; item: InboxItem; analysisReady: boolean }) {
  const queryClient = useQueryClient();
  const analyze = useMutation({
    mutationFn: (mode: 'direction' | 'meeting_summary' | 'audio_to_paper') =>
      analyzeInboxItem(projectId, item.id, mode),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['research-inbox', projectId] }),
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              {item.source_type === 'audio_transcript' ? (
                <FileAudio className="h-4 w-4" />
              ) : (
                <MessageSquareText className="h-4 w-4" />
              )}
              {item.title}
            </CardTitle>
            <p className="mt-1 text-xs text-muted">
              {item.sender || '未注明发送者'} · {new Date(item.created_at).toLocaleString()}
              {item.original_filename ? ` · ${item.original_filename}` : ''}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => analyze.mutate('direction')}
              disabled={!analysisReady || analyze.isPending}
            >
              <WandSparkles className="mr-1.5 h-3.5 w-3.5" /> 提取方向
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => analyze.mutate('meeting_summary')}
              disabled={!analysisReady || analyze.isPending}
            >
              <ClipboardList className="mr-1.5 h-3.5 w-3.5" /> 会议总结
            </Button>
            <Button
              size="sm"
              onClick={() => analyze.mutate('audio_to_paper')}
              loading={analyze.isPending && analyze.variables === 'audio_to_paper'}
              disabled={!analysisReady || analyze.isPending}
            >
              <FileText className="mr-1.5 h-3.5 w-3.5" /> 语音转论文
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <details>
          <summary className="cursor-pointer text-xs font-medium text-muted">查看原始内容</summary>
          <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-surface-2 p-3 text-xs text-text">
            {item.content_text}
          </pre>
        </details>
        {item.agent_run_id && (
          <InboxAnalysis projectId={projectId} runId={item.agent_run_id} />
        )}
        {analyze.error && (
          <p className="rounded-md bg-danger-bg p-2 text-xs text-danger">
            {analyze.error instanceof Error ? analyze.error.message : '分析启动失败'}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function WorkflowCard({
  icon: Icon,
  title,
  text,
}: {
  icon: typeof WandSparkles;
  title: string;
  text: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-text">
        <Icon className="h-4 w-4 text-accent" /> {title}
      </div>
      <p className="mt-2 text-xs leading-5 text-muted">{text}</p>
    </div>
  );
}

function InboxAnalysis({ projectId, runId }: { projectId: string; runId: string }) {
  const run = useQuery({
    queryKey: ['agent-run', projectId, runId],
    queryFn: () => getAgentRun(projectId, runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'running' ? 1500 : false;
    },
  });
  const message = run.data?.output_json?.message;

  if (!run.data || run.data.status === 'queued' || run.data.status === 'running') {
    return (
      <div className="flex items-center gap-2 rounded-md bg-info-bg p-3 text-xs text-info">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> AI 正在提取研究方向…
      </div>
    );
  }
  if (run.data.status === 'failed') {
    return (
      <div className="rounded-md bg-danger-bg p-3 text-xs text-danger">
        {run.data.error_json?.message || '分析失败，请先在设置中检测模型连接。'}
      </div>
    );
  }
  return (
    <div className="rounded-md border border-border bg-surface-2 p-4">
      <div className="mb-2 text-xs font-semibold text-text">AI 方向总结</div>
      <div className="whitespace-pre-wrap text-sm leading-6 text-text">
        {typeof message === 'string' ? message : '分析已完成，但模型没有返回文本。'}
      </div>
    </div>
  );
}

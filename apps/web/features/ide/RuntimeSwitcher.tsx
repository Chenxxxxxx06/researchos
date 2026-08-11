'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { LucideIcon } from 'lucide-react';
import {
  CheckCircle2,
  ChevronDown,
  FolderCog,
  FolderOpen,
  KeyRound,
  Laptop,
  Loader2,
  RotateCcw,
  Server,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { listSSHProfiles, saveSSHProfile, testSSHProfile, type SSHProfileInput } from '@/lib/api/ssh';
import {
  getLocalWorkspaceConfig,
  resetLocalWorkspace,
  setLocalWorkspace,
  type LocalWorkspaceConfig,
} from '@/lib/api/workspace';

interface RuntimeSwitcherProps {
  projectId: string;
  profileId: string | null;
  onChange: (profileId: string | null) => void;
  onWorkspaceChange: () => void;
}

export function RuntimeSwitcher({
  projectId,
  profileId,
  onChange,
  onWorkspaceChange,
}: RuntimeSwitcherProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [formMode, setFormMode] = useState<'ssh' | 'local' | null>(null);
  const [sshForm, setSSHForm] = useState<SSHProfileInput>(emptyProfile());
  const [localPath, setLocalPath] = useState('');

  const profiles = useQuery({
    queryKey: ['ssh-profiles', projectId],
    queryFn: () => listSSHProfiles(projectId),
  });
  const localWorkspace = useQuery({
    queryKey: ['local-workspace', projectId],
    queryFn: () => getLocalWorkspaceConfig(projectId),
  });
  const activeSSH = profiles.data?.find((item) => item.id === profileId);

  const activateLocalConfig = (config: LocalWorkspaceConfig) => {
    queryClient.setQueryData(['local-workspace', projectId], config);
    void queryClient.invalidateQueries({
      predicate: (query) => query.queryKey.includes(projectId),
    });
    onChange(null);
    onWorkspaceChange();
    setFormMode(null);
    setOpen(false);
  };

  const selectLocal = useMutation({
    mutationFn: (rootPath: string) => setLocalWorkspace(projectId, rootPath),
    onSuccess: activateLocalConfig,
  });
  const resetLocal = useMutation({
    mutationFn: () => resetLocalWorkspace(projectId),
    onSuccess: activateLocalConfig,
  });
  const saveSSH = useMutation({
    mutationFn: () => saveSSHProfile(projectId, sshForm),
    onSuccess: (profile) => {
      void queryClient.invalidateQueries({ queryKey: ['ssh-profiles', projectId] });
      onChange(profile.id);
      onWorkspaceChange();
      setFormMode(null);
      setOpen(false);
    },
  });
  const testSSH = useMutation({
    mutationFn: (id: string) => testSSHProfile(projectId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ssh-profiles', projectId] }),
  });

  const localRoot = localWorkspace.data?.root ?? '加载本地工作区…';
  const activeLabel = activeSSH
    ? `${activeSSH.name} · ${activeSSH.username}@${activeSSH.host}`
    : localRoot;
  const mutationError = selectLocal.error ?? resetLocal.error;

  return (
    <div className="relative z-30 flex h-11 shrink-0 items-center justify-between border-b border-border bg-surface px-3">
      <div className="flex min-w-0 items-center gap-2">
        <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-faint">Workspace</span>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="flex h-7 min-w-0 max-w-[36rem] items-center gap-2 border border-border bg-bg px-2.5 text-[11px] font-medium text-text hover:bg-surface-2"
        >
          {activeSSH ? (
            <Server className="h-3.5 w-3.5 shrink-0 text-success" />
          ) : (
            <FolderOpen className="h-3.5 w-3.5 shrink-0 text-accent" />
          )}
          <span className="truncate font-mono">{activeLabel}</span>
          <ChevronDown className="h-3 w-3 shrink-0 text-faint" />
        </button>
        {activeSSH && (
          <span className="flex shrink-0 items-center gap-1 text-[9px] text-success">
            <ShieldCheck className="h-3 w-3" />主机密钥已校验
          </span>
        )}
        {!activeSSH && localWorkspace.data && !localWorkspace.data.available && (
          <span className="text-[9px] text-danger">目录不可用，请重新选择</span>
        )}
      </div>
      <p className="hidden text-[9px] text-faint xl:block">
        本地：文件 + Agent 补丁 + Git · SSH：SFTP + 审计终端
      </p>

      {open && (
        <div className="absolute left-20 top-9 w-[42rem] border border-border bg-overlay p-3 shadow-elev3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-text">选择 AI IDE 工作区</p>
              <p className="mt-1 text-[9px] text-muted">切换时会关闭当前编辑缓冲区，文件树、终端、Git 和 Coding Agent 将同时切换。</p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="p-1 text-muted">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          {formMode === null && (
            <div className="mt-3 space-y-2">
              <div className="flex items-stretch gap-2">
                <RuntimeOption
                  active={!profileId}
                  icon={Laptop}
                  title={localWorkspace.data?.uses_default ? 'ResearchOS 托管工作区' : '本地文件夹'}
                  detail={localRoot}
                  onClick={() => {
                    onChange(null);
                    onWorkspaceChange();
                    setOpen(false);
                  }}
                />
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-auto"
                  onClick={() => {
                    setLocalPath(localWorkspace.data?.uses_default ? '' : (localWorkspace.data?.root ?? ''));
                    setFormMode('local');
                  }}
                >
                  <FolderCog className="mr-1 h-3.5 w-3.5" />设置文件夹
                </Button>
              </div>

              {profiles.data?.map((profile) => (
                <div key={profile.id} className="flex items-stretch gap-2">
                  <RuntimeOption
                    active={profileId === profile.id}
                    icon={Server}
                    title={profile.name}
                    detail={`${profile.username}@${profile.host}:${profile.port} · ${profile.default_workdir}`}
                    verified={Boolean(profile.last_verified_at)}
                    onClick={() => {
                      onChange(profile.id);
                      onWorkspaceChange();
                      setOpen(false);
                    }}
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    className="h-auto"
                    disabled={testSSH.isPending}
                    onClick={() => testSSH.mutate(profile.id)}
                  >
                    {testSSH.isPending && testSSH.variables === profile.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : '测试'}
                  </Button>
                </div>
              ))}

              <Button
                size="sm"
                variant="secondary"
                className="w-full"
                onClick={() => {
                  setSSHForm(emptyProfile());
                  setFormMode('ssh');
                }}
              >
                <Server className="mr-1 h-3.5 w-3.5" />添加 SSH 工作区
              </Button>
              {testSSH.data && (
                <p className="border border-success/20 bg-success-bg p-2 text-[10px] text-success">
                  {testSSH.data.message} · {testSSH.data.latency_ms} ms
                </p>
              )}
              {testSSH.error && <ErrorText error={testSSH.error} fallback="连接测试失败" />}
            </div>
          )}

          {formMode === 'local' && (
            <form
              className="mt-3 space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                selectLocal.mutate(localPath.trim());
              }}
            >
              <Field label="本地项目文件夹的绝对路径">
                <Input
                  autoFocus
                  required
                  value={localPath}
                  onChange={(event) => setLocalPath(event.target.value)}
                  placeholder="G:\\code\\my-research 或 /home/me/my-research"
                  className="font-mono"
                />
              </Field>
              <p className="text-[10px] leading-5 text-muted">
                路径由运行 ResearchOS API 的这台电脑解析。出于浏览器安全限制，网页不能读取系统文件夹选择器返回的真实绝对路径，因此首次需要手动填写；之后可从最近目录一键切换。
              </p>

              {(localWorkspace.data?.recent_roots.length ?? 0) > 0 && (
                <div>
                  <p className="text-[9px] font-semibold uppercase tracking-wider text-faint">最近使用</p>
                  <div className="mt-1 space-y-1">
                    {localWorkspace.data?.recent_roots.map((root) => (
                      <button
                        key={root}
                        type="button"
                        onClick={() => setLocalPath(root)}
                        className="block w-full truncate border border-border bg-bg px-2 py-1.5 text-left font-mono text-[10px] text-muted hover:border-accent hover:text-text"
                      >
                        {root}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {mutationError && <ErrorText error={mutationError} fallback="无法切换本地文件夹" />}
              <div className="flex flex-wrap gap-2">
                <Button size="sm" type="submit" loading={selectLocal.isPending} disabled={!localPath.trim()}>
                  <FolderOpen className="mr-1 h-3.5 w-3.5" />使用该文件夹
                </Button>
                {!localWorkspace.data?.uses_default && (
                  <Button
                    size="sm"
                    type="button"
                    variant="secondary"
                    loading={resetLocal.isPending}
                    onClick={() => resetLocal.mutate()}
                  >
                    <RotateCcw className="mr-1 h-3.5 w-3.5" />恢复托管工作区
                  </Button>
                )}
                <Button size="sm" type="button" variant="ghost" onClick={() => setFormMode(null)}>
                  取消
                </Button>
              </div>
            </form>
          )}

          {formMode === 'ssh' && (
            <form
              className="mt-3 space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                saveSSH.mutate();
              }}
            >
              <div className="grid grid-cols-2 gap-3">
                <Field label="配置名称">
                  <Input required value={sshForm.name} onChange={(event) => setSSHForm({ ...sshForm, name: event.target.value })} />
                </Field>
                <Field label="认证方式">
                  <select
                    value={sshForm.auth_type}
                    onChange={(event) => setSSHForm({ ...sshForm, auth_type: event.target.value as 'password' | 'ssh_key' })}
                    className="h-10 w-full border border-border-strong bg-surface px-3 text-xs"
                  >
                    <option value="ssh_key">SSH private key</option>
                    <option value="password">Password</option>
                  </select>
                </Field>
                <Field label="主机">
                  <Input required value={sshForm.host} onChange={(event) => setSSHForm({ ...sshForm, host: event.target.value })} />
                </Field>
                <Field label="端口">
                  <Input required type="number" value={sshForm.port} onChange={(event) => setSSHForm({ ...sshForm, port: Number(event.target.value) })} />
                </Field>
                <Field label="用户名">
                  <Input required value={sshForm.username} onChange={(event) => setSSHForm({ ...sshForm, username: event.target.value })} />
                </Field>
                <Field label="远端项目绝对路径">
                  <Input required placeholder="/srv/research/project" value={sshForm.default_workdir} onChange={(event) => setSSHForm({ ...sshForm, default_workdir: event.target.value })} />
                </Field>
              </div>
              <Field label={sshForm.auth_type === 'ssh_key' ? '私钥内容' : '密码'}>
                <textarea
                  required
                  value={sshForm.secret ?? ''}
                  onChange={(event) => setSSHForm({ ...sshForm, secret: event.target.value })}
                  className="min-h-20 w-full border border-border-strong bg-surface p-2 font-mono text-[10px]"
                  placeholder={sshForm.auth_type === 'ssh_key' ? '-----BEGIN OPENSSH PRIVATE KEY-----' : '••••••••'}
                />
              </Field>
              {sshForm.auth_type === 'ssh_key' && (
                <Field label="私钥口令（如有）">
                  <Input type="password" value={sshForm.key_passphrase ?? ''} onChange={(event) => setSSHForm({ ...sshForm, key_passphrase: event.target.value })} />
                </Field>
              )}
              <Field label="known_hosts 条目">
                <textarea
                  required
                  value={sshForm.known_hosts}
                  onChange={(event) => setSSHForm({ ...sshForm, known_hosts: event.target.value })}
                  className="min-h-16 w-full border border-border-strong bg-surface p-2 font-mono text-[10px]"
                  placeholder="[host]:22 ssh-ed25519 AAAA…"
                />
              </Field>
              <p className="flex items-start gap-2 text-[10px] leading-4 text-muted">
                <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                密码或私钥加密保存；连接必须匹配 known_hosts，不提供关闭主机密钥校验的选项。
              </p>
              {saveSSH.error && <ErrorText error={saveSSH.error} fallback="保存失败" />}
              <div className="flex gap-2">
                <Button size="sm" type="submit" loading={saveSSH.isPending}>加密保存</Button>
                <Button size="sm" type="button" variant="secondary" onClick={() => setFormMode(null)}>取消</Button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}

function RuntimeOption({
  active,
  icon: Icon,
  title,
  detail,
  verified,
  onClick,
}: {
  active: boolean;
  icon: LucideIcon;
  title: string;
  detail: string;
  verified?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-w-0 flex-1 items-center gap-3 border p-3 text-left ${active ? 'border-accent bg-accent/5' : 'border-border hover:bg-surface-2'}`}
    >
      <Icon className="h-4 w-4 shrink-0 text-accent" />
      <span className="min-w-0">
        <span className="flex items-center gap-2 text-xs font-medium text-text">
          {title}{verified && <CheckCircle2 className="h-3 w-3 text-success" />}
        </span>
        <span className="mt-0.5 block truncate font-mono text-[9px] text-muted">{detail}</span>
      </span>
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <Label>{label}</Label>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function ErrorText({ error, fallback }: { error: unknown; fallback: string }) {
  return <p className="border border-danger/20 bg-danger-bg p-2 text-[10px] text-danger">{error instanceof Error ? error.message : fallback}</p>;
}

function emptyProfile(): SSHProfileInput {
  return {
    name: '',
    host: '',
    port: 22,
    username: '',
    auth_type: 'ssh_key',
    secret: '',
    key_passphrase: '',
    known_hosts: '',
    default_workdir: '',
  };
}

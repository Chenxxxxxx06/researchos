'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, FolderPlus } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiError } from '@/lib/api/client';
import { createProject } from '@/lib/api/projects';
import { useI18n } from '@/lib/i18n';

const schema = z.object({ name: z.string().trim().min(1) });

export function CreateProjectDialog({ organizationId }: { organizationId: string }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [field, setField] = useState('');
  const [fieldError, setFieldError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => createProject({
      organization_id: organizationId,
      name: name.trim(),
      field: field.trim() || undefined,
    }),
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ['projects', organizationId] });
      setOpen(false);
      setName('');
      setField('');
      router.push(`/projects/${project.id}/overview`);
    },
  });

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFieldError(null);
    if (!schema.safeParse({ name }).success) {
      setFieldError(zh ? '请输入项目名称。' : 'Enter a project name.');
      return;
    }
    mutation.mutate();
  }

  const serverError = mutation.error instanceof ApiError ? mutation.error.message : null;

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <FolderPlus className="h-4 w-4" aria-hidden="true" />
        {zh ? '新建项目' : 'New project'}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader className="border-b border-border p-5">
            <div>
              <DialogTitle>{zh ? '创建研究项目' : 'Create research project'}</DialogTitle>
              <DialogDescription>
                {zh ? '项目将承载资料、任务、代码、实验和论文的完整证据链。' : 'A project connects evidence, missions, code, experiments, and papers.'}
              </DialogDescription>
            </div>
            <DialogClose />
          </DialogHeader>
          <form onSubmit={onSubmit} noValidate>
            <div className="space-y-4 p-5">
              <div>
                <Label htmlFor="project-name">{zh ? '项目名称' : 'Project name'}</Label>
                <Input
                  id="project-name"
                  data-autofocus
                  className="mt-1.5"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder={zh ? '例如：多模态模型可靠性研究' : 'e.g. Reliable multimodal models'}
                  aria-invalid={Boolean(fieldError)}
                />
              </div>
              <div>
                <Label htmlFor="project-field">{zh ? '研究领域（可选）' : 'Research field (optional)'}</Label>
                <Input
                  id="project-field"
                  className="mt-1.5"
                  value={field}
                  onChange={(event) => setField(event.target.value)}
                  placeholder="Machine Learning / HCI / Medical AI"
                />
              </div>
              {(fieldError || serverError) && <p role="alert" className="text-sm text-danger">{fieldError ?? serverError}</p>}
            </div>
            <DialogFooter className="border-t border-border p-4">
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>{zh ? '取消' : 'Cancel'}</Button>
              <Button type="submit" loading={mutation.isPending} disabled={!name.trim()}>
                {zh ? '创建并进入' : 'Create and open'} <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { z } from 'zod';

import { createProject } from '@/lib/api/projects';
import { ApiError } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const schema = z.object({ name: z.string().min(1, 'Project name is required.') });

export function CreateProjectDialog({ organizationId }: { organizationId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [field, setField] = useState('');
  const [fieldError, setFieldError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createProject({
        organization_id: organizationId,
        name,
        field: field || undefined,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['projects', organizationId] });
      setOpen(false);
      setName('');
      setField('');
    },
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFieldError(null);
    const parsed = schema.safeParse({ name });
    if (!parsed.success) {
      setFieldError(parsed.error.issues[0]?.message ?? 'Invalid input.');
      return;
    }
    mutation.mutate();
  }

  if (!open) {
    return <Button onClick={() => setOpen(true)}>New project</Button>;
  }

  const serverError = mutation.error instanceof ApiError ? mutation.error.message : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg border border-neutral-200 bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-base font-semibold">Create project</h2>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div>
            <Label htmlFor="project-name">Name</Label>
            <Input id="project-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="project-field">Research field (optional)</Label>
            <Input id="project-field" value={field} onChange={(e) => setField(e.target.value)} />
          </div>
          {(fieldError || serverError) && (
            <p className="text-sm text-red-600">{fieldError ?? serverError}</p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

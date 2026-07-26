'use client';

/** Coding-chat composer: mod+Enter submits; disabled while a run is live. */

import { Send } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useI18n } from '@/lib/i18n';

export interface ComposerProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  busy?: boolean;
}

export function Composer({ onSend, disabled = false, busy = false }: ComposerProps) {
  const { t } = useI18n();
  const [text, setText] = useState('');

  const submit = () => {
    const value = text.trim();
    if (!value || disabled) return;
    onSend(value);
    setText('');
  };

  return (
    <form
      className="flex items-end gap-2 border-t border-border bg-surface p-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t('ide.composerPlaceholder')}
        disabled={disabled}
        rows={2}
        className="min-h-0 resize-none"
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            e.preventDefault();
            submit();
          }
        }}
      />
      <Button
        type="submit"
        size="icon"
        disabled={disabled || text.trim().length === 0}
        loading={busy}
        aria-label={t('ide.send')}
      >
        {!busy && <Send className="h-4 w-4" aria-hidden="true" />}
      </Button>
    </form>
  );
}

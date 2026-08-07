'use client';

import { Mic, Square, Waves } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';

interface RecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}

interface RecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<RecognitionResultLike>;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: RecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type RecognitionConstructor = new () => SpeechRecognitionLike;

export function StreamingVoiceCapture({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const base = useRef('');
  const committed = useRef('');
  const recording = useRef(false);
  const [active, setActive] = useState(false);
  const [interim, setInterim] = useState('');
  const [error, setError] = useState('');
  const [supported, setSupported] = useState(true);

  useEffect(() => () => recognition.current?.stop(), []);

  function start() {
    const scope = window as typeof window & {
      SpeechRecognition?: RecognitionConstructor;
      webkitSpeechRecognition?: RecognitionConstructor;
    };
    const Constructor = scope.SpeechRecognition ?? scope.webkitSpeechRecognition;
    if (!Constructor) {
      setSupported(false);
      return;
    }
    base.current = value.trim();
    committed.current = '';
    setInterim('');
    setError('');
    const instance = new Constructor();
    instance.continuous = true;
    instance.interimResults = true;
    instance.lang = 'zh-CN';
    instance.onresult = (event) => {
      let live = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (result.isFinal) committed.current += result[0].transcript;
        else live += result[0].transcript;
      }
      setInterim(live);
      onChange([base.current, committed.current, live].filter(Boolean).join('\n'));
    };
    instance.onerror = (event) => {
      if (event.error !== 'no-speech') setError(`语音识别中断：${event.error}`);
    };
    instance.onend = () => {
      if (recording.current) {
        try { instance.start(); } catch { /* browser is already restarting */ }
      }
    };
    recognition.current = instance;
    recording.current = true;
    setActive(true);
    instance.start();
  }

  function stop() {
    recording.current = false;
    setActive(false);
    setInterim('');
    recognition.current?.stop();
    recognition.current = null;
  }

  if (!supported) return <p data-testid="streaming-voice-capture" className="border-l-2 border-warn bg-warn-bg px-3 py-2 text-[10px] leading-4 text-warn">当前浏览器不支持实时语音识别。请使用 Chrome/Edge，或粘贴已有转写稿。</p>;
  return <div data-testid="streaming-voice-capture" className={`rounded-md border p-3 ${active ? 'border-danger bg-danger-bg/40' : 'border-border-strong bg-surface-2'}`}><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2">{active ? <Waves className="h-4 w-4 animate-pulse text-danger" /> : <Mic className="h-4 w-4 text-muted" />}<div><p className="text-xs font-medium text-text">{active ? '实时转写中' : '流式语音记录'}</p><p className="text-[9px] text-faint">{active ? '临时结果会实时显示，停止后可编辑再保存' : '浏览器麦克风 → 实时文本 → Research Inbox'}</p></div></div>{active ? <Button type="button" size="sm" variant="destructive" onClick={stop}><Square className="h-3 w-3" />停止</Button> : <Button type="button" size="sm" variant="secondary" onClick={start}><Mic className="h-3 w-3" />开始说话</Button>}</div>{interim && <p className="mt-2 border-l border-danger/50 pl-2 text-[10px] italic leading-4 text-muted">{interim}</p>}{error && <p className="mt-2 text-[10px] text-danger">{error}</p>}</div>;
}

import { ChatMessage, Feedback } from '@/api';
import { CopyToClipboard } from '@/components/copy-to-clipboard';
import { Card } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import _ from 'lodash';
import { Bot, LoaderCircle } from 'lucide-react';
import { useMemo } from 'react';
import { CitationSources, ResponseMetaBar } from './message-citations';
import type { ResponseMeta } from './message-citations';
import { MessageFeedback } from './message-feedback';
import { MessagePartAi } from './message-part-ai';
import { MessageReference } from './message-reference';
import { MessageTimestamp } from './message-timestamp';

export const MessagePartsAi = ({
  pending,
  loading,
  parts,
  hanldeMessageFeedback,
}: {
  pending: boolean;
  loading: boolean;
  parts: ChatMessage[];
  hanldeMessageFeedback: (part: ChatMessage, feedback: Feedback) => void;
}) => {
  const references = useMemo(
    () => parts.findLast((part) => part.references)?.references || [],
    [parts],
  );

  const responseMeta = useMemo((): ResponseMeta | null => {
    const last = parts.findLast((p) => p.type === 'stop' || p.type === 'message');
    if (!last?.metadata) return null;
    const m = last.metadata as Record<string, unknown>;
    return {
      model_used: m.model_used as string | undefined,
      latency_ms: m.latency_ms as number | undefined,
      retrieval_ms: m.retrieval_ms as number | undefined,
      generation_ms: m.generation_ms as number | undefined,
      tokens_used: m.tokens_used as ResponseMeta['tokens_used'],
      grounding_score: m.grounding_score as number | undefined,
      num_sources: references.length || undefined,
    };
  }, [parts, references]);

  return (
    <div className="flex w-max flex-row gap-4">
      <div>
        <div className="bg-muted text-muted-foreground relative flex size-12 flex-col justify-center rounded-full">
          {loading && (
            <LoaderCircle className="absolute -left-1 size-14 animate-spin opacity-20" />
          )}
          <Bot className={cn('size-6 self-center')} />
        </div>
      </div>
      <div className="flex max-w-sm flex-col gap-1 sm:max-w-lg md:max-w-2xl lg:max-w-3xl xl:max-w-4xl">
        <Card className="dark:border-card/0 block gap-0 px-4 py-4 text-sm">
          {pending ? (
            <div className="flex flex-row gap-2 py-2">
              <div className="bg-muted-foreground animate-caret-blink size-2 rounded-full delay-0"></div>
              <div className="bg-muted-foreground animate-caret-blink size-2 rounded-full delay-200"></div>
              <div className="bg-muted-foreground animate-caret-blink size-2 rounded-full delay-400"></div>
            </div>
          ) : (
            <>
              {parts.map((part, index) => (
                <MessagePartAi
                  key={`${index}-${part.id}`}
                  part={part}
                  loading={loading}
                />
              ))}
              {responseMeta && (responseMeta.model_used || responseMeta.latency_ms != null || responseMeta.tokens_used || responseMeta.grounding_score != null) && (
                <ResponseMetaBar meta={responseMeta} />
              )}
              {!_.isEmpty(references) && (
                <CitationSources references={references} />
              )}
            </>
          )}
        </Card>
        <div className="flex flex-row items-center gap-2">
          <MessageTimestamp parts={parts} className="mr-2" />
          <Separator
            orientation="vertical"
            className="data-[orientation=vertical]:h-4"
          />
          {!_.isEmpty(references) && (
            <>
              <MessageReference references={references} />
              <Separator
                orientation="vertical"
                className="data-[orientation=vertical]:h-4"
              />
            </>
          )}
          <MessageFeedback
            parts={parts}
            hanldeMessageFeedback={hanldeMessageFeedback}
          />
          <Separator
            orientation="vertical"
            className="data-[orientation=vertical]:h-4"
          />
          <CopyToClipboard
            variant="ghost"
            className="text-muted-foreground"
            text={parts.map((part) => part.data).join('')}
          />
        </div>
      </div>
    </div>
  );
};

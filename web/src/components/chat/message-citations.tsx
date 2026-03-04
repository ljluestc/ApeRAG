'use client';

import { Reference } from '@/api';
import { Badge } from '@/components/ui/badge';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import { BookOpen, ChevronDown, Clock, Cpu, Hash } from 'lucide-react';
import { useCallback, useState } from 'react';

export type ResponseMeta = {
  model_used?: string;
  latency_ms?: number;
  retrieval_ms?: number;
  generation_ms?: number;
  tokens_used?: {
    prompt?: number;
    completion?: number;
    total?: number;
  };
  grounding_score?: number;
  num_sources?: number;
};

export const CitationBadge = ({
  index,
  onClick,
}: {
  index: number;
  onClick?: () => void;
}) => {
  return (
    <Badge
      variant="secondary"
      className="bg-primary/15 text-primary hover:bg-primary/25 cursor-pointer rounded px-1.5 py-0 font-mono text-[10px] transition-colors"
      onClick={onClick}
    >
      S{index}
    </Badge>
  );
};

export const ResponseMetaBar = ({ meta }: { meta: ResponseMeta }) => {
  const latencyColor =
    (meta.latency_ms || 0) < 2000
      ? 'text-green-500'
      : (meta.latency_ms || 0) < 5000
        ? 'text-yellow-500'
        : 'text-red-500';

  return (
    <div className="bg-muted/50 mt-3 flex flex-wrap items-center gap-3 rounded-lg px-3 py-2 text-xs">
      {meta.model_used && (
        <div className="flex items-center gap-1">
          <Cpu className="text-muted-foreground size-3" />
          <span className="text-muted-foreground">Model:</span>
          <span className="text-primary font-medium">{meta.model_used}</span>
        </div>
      )}
      {meta.latency_ms != null && (
        <div className="flex items-center gap-1">
          <Clock className="text-muted-foreground size-3" />
          <span className="text-muted-foreground">Latency:</span>
          <span className={cn('font-medium', latencyColor)}>
            {meta.latency_ms.toFixed(0)}ms
          </span>
          {(meta.retrieval_ms != null || meta.generation_ms != null) && (
            <span className="text-muted-foreground">
              (
              {[
                meta.retrieval_ms != null
                  ? `retrieval ${meta.retrieval_ms.toFixed(0)}ms`
                  : null,
                meta.generation_ms != null
                  ? `LLM ${meta.generation_ms.toFixed(0)}ms`
                  : null,
              ]
                .filter(Boolean)
                .join(' + ')}
              )
            </span>
          )}
        </div>
      )}
      {meta.tokens_used && (
        <div className="flex items-center gap-1">
          <Hash className="text-muted-foreground size-3" />
          <span className="text-muted-foreground">Tokens:</span>
          <span className="text-primary font-medium">
            {meta.tokens_used.total ||
              (meta.tokens_used.prompt || 0) +
                (meta.tokens_used.completion || 0)}
          </span>
          <span className="text-muted-foreground">
            ({meta.tokens_used.prompt || 0} in /{' '}
            {meta.tokens_used.completion || 0} out)
          </span>
        </div>
      )}
      {meta.grounding_score != null && (
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">Grounding:</span>
          <span className="text-primary font-medium">
            {(meta.grounding_score * 100).toFixed(0)}%
          </span>
        </div>
      )}
      {meta.num_sources != null && (
        <div className="flex items-center gap-1">
          <BookOpen className="text-muted-foreground size-3" />
          <span className="text-muted-foreground">Sources:</span>
          <span className="text-primary font-medium">
            {meta.num_sources} chunks
          </span>
        </div>
      )}
    </div>
  );
};

export const CitationSources = ({
  references,
}: {
  references: Reference[];
}) => {
  const [highlightId, setHighlightId] = useState<number | null>(null);

  const handleCitationClick = useCallback((index: number) => {
    setHighlightId(index);
    setTimeout(() => setHighlightId(null), 1500);
  }, []);

  if (!references?.length) return null;

  return (
    <Collapsible defaultOpen>
      <CollapsibleTrigger className="hover:bg-accent flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors">
        <BookOpen className="size-4" />
        <span>
          Sources ({references.length})
        </span>
        <ChevronDown className="ml-auto size-4 transition-transform [[data-state=open]>&]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="bg-muted/30 flex flex-col gap-px rounded-lg">
          {references.map((ref, index) => (
            <div
              key={index}
              data-citation-id={index + 1}
              className={cn(
                'flex items-baseline gap-2 px-3 py-2 text-xs transition-colors',
                highlightId === index + 1 && 'bg-primary/10',
              )}
            >
              <CitationBadge
                index={index + 1}
                onClick={() => handleCitationClick(index + 1)}
              />
              <Badge
                variant="outline"
                className="shrink-0 font-mono text-[10px]"
              >
                {((ref.score || 0) * 100).toFixed(0)}%
              </Badge>
              <span className="text-muted-foreground line-clamp-2 flex-1 font-mono">
                {ref.metadata?.filename || ref.metadata?.type || 'Document'}
                {ref.metadata?.page_number
                  ? ` p.${ref.metadata.page_number}`
                  : ''}
              </span>
              {ref.metadata?.section_title && (
                <span className="text-muted-foreground truncate italic">
                  — {ref.metadata.section_title}
                </span>
              )}
            </div>
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

/**
 * Inject citation badges into markdown text.
 * Replaces patterns like [Source 1], [Document 2], [Source 1, 2, 3] with CitationBadge markup.
 */
export const injectCitationBadges = (text: string): string => {
  if (!text) return text;
  let result = text.replace(
    /\[(?:Source|Document)\s*\d+(?:\s*,\s*(?:(?:Source|Document)\s*)?\d+)+\]/gi,
    (match) => {
      const nums = match.match(/\d+/g);
      if (!nums) return match;
      const seen = new Set<string>();
      return nums
        .filter((n) => {
          if (seen.has(n)) return false;
          seen.add(n);
          return true;
        })
        .map((n) => `**[S${n}]**`)
        .join(' ');
    },
  );
  result = result.replace(
    /\[(?:Source|Document)\s*(\d+)\]/gi,
    (_, n) => `**[S${n}]**`,
  );
  return result;
};

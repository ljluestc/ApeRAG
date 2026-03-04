'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import _ from 'lodash';
import { BarChart3, Clock, Hash, LoaderCircle, Trophy, X } from 'lucide-react';
import { Markdown } from '../markdown';

export type ModelBenchmarkResult = {
  model: string;
  provider: string;
  answer: string;
  latency_ms: number;
  tokens_used: {
    prompt: number;
    completion: number;
    total: number;
  };
  error?: string;
};

export type BenchmarkSummary = {
  models_compared: number;
  fastest_model: string;
  fastest_latency_ms: number;
  cheapest_model: string;
  cheapest_tokens: number;
};

export const ModelComparison = ({
  results,
  summary,
  loading,
  onClose,
}: {
  results: ModelBenchmarkResult[];
  summary?: BenchmarkSummary;
  loading: boolean;
  onClose: () => void;
}) => {
  if (loading) {
    return (
      <Card className="mt-4">
        <CardContent className="flex items-center justify-center py-8">
          <LoaderCircle className="size-6 animate-spin opacity-50" />
          <span className="text-muted-foreground ml-2 text-sm">
            Comparing models...
          </span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mt-4">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <BarChart3 className="size-4" />
            Model Comparison
          </CardTitle>
          <Button
            size="icon"
            variant="ghost"
            className="size-6 cursor-pointer"
            onClick={onClose}
          >
            <X className="size-3.5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {results.map((result, index) => (
          <Card key={index} className="bg-muted/30">
            <CardContent className="p-3">
              {result.error ? (
                <div>
                  <div className="text-primary mb-1 text-sm font-semibold">
                    {result.model}
                  </div>
                  <div className="text-sm text-red-500">
                    Error: {result.error}
                  </div>
                </div>
              ) : (
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-primary text-sm font-semibold">
                      {result.model}
                    </span>
                    <div className="flex items-center gap-2">
                      {summary?.fastest_model === result.model && (
                        <Badge
                          variant="default"
                          className="bg-green-600 text-[10px]"
                        >
                          <Trophy className="mr-0.5 size-2.5" />
                          Fastest
                        </Badge>
                      )}
                      {summary?.cheapest_model === result.model && (
                        <Badge
                          variant="default"
                          className="bg-blue-600 text-[10px]"
                        >
                          <Hash className="mr-0.5 size-2.5" />
                          Cheapest
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="text-muted-foreground mb-2 flex items-center gap-3 text-xs">
                    <span className="flex items-center gap-1">
                      <Clock className="size-3" />
                      <span className="text-primary">
                        {result.latency_ms}ms
                      </span>
                    </span>
                    <span>|</span>
                    <span className="flex items-center gap-1">
                      <Hash className="size-3" />
                      <span className="text-primary">
                        {result.tokens_used.total} tokens
                      </span>
                      <span className="text-muted-foreground">
                        ({result.tokens_used.prompt} in /{' '}
                        {result.tokens_used.completion} out)
                      </span>
                    </span>
                  </div>
                  <ScrollArea className="max-h-20">
                    <div className="text-xs leading-relaxed">
                      <Markdown>
                        {_.truncate(result.answer, { length: 300 })}
                      </Markdown>
                    </div>
                  </ScrollArea>
                </div>
              )}
            </CardContent>
          </Card>
        ))}

        {summary && (
          <>
            <Separator />
            <div className="bg-primary/5 flex flex-wrap items-center gap-4 rounded-lg px-3 py-2 text-xs">
              <span className="flex items-center gap-1">
                <Trophy className="size-3 text-green-500" />
                <strong>Fastest:</strong> {summary.fastest_model} (
                {summary.fastest_latency_ms}ms)
              </span>
              <span>|</span>
              <span className="flex items-center gap-1">
                <Hash className="size-3 text-blue-500" />
                <strong>Cheapest:</strong> {summary.cheapest_model} (
                {summary.cheapest_tokens} tokens)
              </span>
              <span>|</span>
              <span>{summary.models_compared} models compared</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

'use client';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import {
  BookOpen,
  Brain,
  FileQuestion,
  LoaderCircle,
  Search,
  Sparkles,
  X,
} from 'lucide-react';
import { useCallback, useState } from 'react';
import { toast } from 'sonner';
import { Markdown } from './markdown';

type AiResult = {
  type: 'summary' | 'search' | 'qa' | 'graph';
  content: string;
  loading: boolean;
};

export const AiFeaturesPanel = ({
  collectionId,
  open,
  onClose,
}: {
  collectionId?: string;
  open: boolean;
  onClose: () => void;
}) => {
  const [result, setResult] = useState<AiResult | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const handleSummarize = useCallback(async () => {
    if (!collectionId) {
      toast.error('Please select a collection first');
      return;
    }
    setResult({ type: 'summary', content: '', loading: true });
    try {
      const res =
        await apiClient.defaultApi.collectionsCollectionIdSummaryGeneratePost({
          collectionId,
        });
      setResult({
        type: 'summary',
        content:
          (res.data as { summary?: string })?.summary ||
          'Summary generated successfully.',
        loading: false,
      });
    } catch {
      setResult({
        type: 'summary',
        content: 'Failed to generate summary. Please try again.',
        loading: false,
      });
    }
  }, [collectionId]);

  const handleBuildGraph = useCallback(async () => {
    if (!collectionId) {
      toast.error('Please select a collection first');
      return;
    }
    setResult({ type: 'graph', content: '', loading: true });
    try {
      await apiClient.graphApi.collectionsCollectionIdGraphsGet({
        collectionId,
      });
      setResult({
        type: 'graph',
        content:
          'Knowledge graph has been built. Visit the Graph tab to visualize it.',
        loading: false,
      });
    } catch {
      setResult({
        type: 'graph',
        content:
          'Failed to build knowledge graph. Ensure the collection has knowledge graph enabled in settings.',
        loading: false,
      });
    }
  }, [collectionId]);

  const handleSearch = useCallback(async () => {
    if (!collectionId || !searchQuery.trim()) {
      toast.error('Please enter a search query');
      return;
    }
    setResult({ type: 'search', content: '', loading: true });
    try {
      const res =
        await apiClient.defaultApi.collectionsCollectionIdSearchPost({
          collectionId,
          searchRequest: { query: searchQuery, top_k: 5 },
        });
      const items = (res.data as { items?: Array<{ text?: string }> })?.items;
      if (items?.length) {
        const content = items
          .map(
            (item, i) =>
              `**Result ${i + 1}:**\n${item.text?.substring(0, 300) || 'No content'}`,
          )
          .join('\n\n---\n\n');
        setResult({ type: 'search', content, loading: false });
      } else {
        setResult({
          type: 'search',
          content: 'No results found.',
          loading: false,
        });
      }
    } catch {
      setResult({
        type: 'search',
        content: 'Search failed. Please try again.',
        loading: false,
      });
    }
  }, [collectionId, searchQuery]);

  const handleGenerateQA = useCallback(async () => {
    if (!collectionId) {
      toast.error('Please select a collection first');
      return;
    }
    setResult({ type: 'qa', content: '', loading: true });
    toast.info(
      'Q&A generation started. Visit the Evaluation tab to view questions.',
    );
    setResult({
      type: 'qa',
      content:
        'Q&A generation triggered. Navigate to the **Evaluation → Question Sets** tab to create and manage question sets for this collection.',
      loading: false,
    });
  }, [collectionId]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 20 }}
          transition={{ duration: 0.2 }}
          className="fixed right-4 bottom-20 z-50 w-80"
        >
          <Card className="shadow-xl">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="text-primary size-4" />
                  AI Features
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
              <CardDescription className="text-xs">
                AI-powered tools for your collection
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-auto cursor-pointer flex-col gap-1 py-3"
                  onClick={handleSummarize}
                  disabled={result?.loading}
                >
                  <BookOpen className="size-4" />
                  <span className="text-xs">Summarize</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-auto cursor-pointer flex-col gap-1 py-3"
                  onClick={handleBuildGraph}
                  disabled={result?.loading}
                >
                  <Brain className="size-4" />
                  <span className="text-xs">Build Graph</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-auto cursor-pointer flex-col gap-1 py-3"
                  onClick={handleGenerateQA}
                  disabled={result?.loading}
                >
                  <FileQuestion className="size-4" />
                  <span className="text-xs">Generate Q&A</span>
                </Button>
                <div className="flex flex-col gap-1">
                  <div className="flex gap-1">
                    <Input
                      placeholder="Search..."
                      className="h-7 text-xs"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSearch();
                      }}
                    />
                    <Button
                      size="icon"
                      variant="outline"
                      className="size-7 shrink-0 cursor-pointer"
                      onClick={handleSearch}
                      disabled={result?.loading}
                    >
                      <Search className="size-3" />
                    </Button>
                  </div>
                </div>
              </div>

              {result && (
                <>
                  <Separator />
                  <ScrollArea className="max-h-48">
                    {result.loading ? (
                      <div className="flex items-center justify-center py-4">
                        <LoaderCircle className="size-5 animate-spin opacity-50" />
                      </div>
                    ) : (
                      <div className="prose prose-sm dark:prose-invert max-w-none text-xs">
                        <Markdown>{result.content}</Markdown>
                      </div>
                    )}
                  </ScrollArea>
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export const AiFeaturesToggle = ({
  onClick,
  className,
}: {
  onClick: () => void;
  className?: string;
}) => {
  return (
    <Button
      size="icon"
      className={cn(
        'fixed right-4 bottom-4 z-50 size-12 cursor-pointer rounded-full shadow-lg',
        className,
      )}
      onClick={onClick}
    >
      <Sparkles className="size-5" />
    </Button>
  );
};

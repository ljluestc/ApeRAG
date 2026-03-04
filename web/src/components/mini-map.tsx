'use client';

import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { ChevronLeft, ChevronRight, Map } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

type HeadingItem = {
  id: string;
  text: string;
  level: number;
};

export const MiniMap = ({
  markdownContent,
  className,
}: {
  markdownContent?: string;
  className?: string;
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const [activeId, setActiveId] = useState<string>('');

  const headings = useMemo(() => {
    if (!markdownContent) return [];
    const lines = markdownContent.split('\n');
    const items: HeadingItem[] = [];
    lines.forEach((line, index) => {
      const match = line.match(/^(#{1,3})\s+(.+)/);
      if (match) {
        const level = match[1].length;
        const text = match[2].replace(/[*_`\[\]]/g, '').trim();
        const id = `heading-${index}-${text.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
        items.push({ id, text, level });
      }
    });
    return items;
  }, [markdownContent]);

  const handleClick = useCallback((heading: HeadingItem) => {
    setActiveId(heading.id);
    // Find the heading element in the rendered markdown
    const allHeadings = document.querySelectorAll('h1, h2, h3');
    for (const el of allHeadings) {
      if (el.textContent?.trim() === heading.text) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        break;
      }
    }
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const text = entry.target.textContent?.trim();
            const found = headings.find((h) => h.text === text);
            if (found) setActiveId(found.id);
          }
        }
      },
      { rootMargin: '-20% 0px -70% 0px' },
    );

    const allHeadings = document.querySelectorAll('h1, h2, h3');
    allHeadings.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [headings]);

  if (!headings.length) return null;

  return (
    <div
      className={cn(
        'border-border bg-background/95 flex flex-col rounded-lg border backdrop-blur-sm transition-all duration-200',
        collapsed ? 'w-10' : 'w-56',
        className,
      )}
    >
      <div className="flex items-center justify-between border-b p-2">
        {!collapsed && (
          <div className="flex items-center gap-1.5 text-xs font-medium">
            <Map className="size-3.5" />
            <span>Mini Map</span>
          </div>
        )}
        <Button
          size="icon"
          variant="ghost"
          className="size-6 cursor-pointer"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? (
            <ChevronRight className="size-3.5" />
          ) : (
            <ChevronLeft className="size-3.5" />
          )}
        </Button>
      </div>

      {!collapsed && (
        <ScrollArea className="max-h-96 px-2 py-1">
          <nav className="flex flex-col gap-0.5">
            {headings.map((heading) => (
              <button
                key={heading.id}
                onClick={() => handleClick(heading)}
                className={cn(
                  'hover:bg-accent truncate rounded px-2 py-1 text-left text-xs transition-colors',
                  heading.level === 1 && 'font-semibold',
                  heading.level === 2 && 'pl-4',
                  heading.level === 3 && 'text-muted-foreground pl-6',
                  activeId === heading.id &&
                    'bg-primary/10 text-primary font-medium',
                )}
              >
                {heading.text}
              </button>
            ))}
          </nav>
        </ScrollArea>
      )}
    </div>
  );
};

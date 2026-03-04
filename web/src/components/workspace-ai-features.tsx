'use client';

import { useParams } from 'next/navigation';
import { useState } from 'react';
import { AiFeaturesPanel, AiFeaturesToggle } from './ai-features-panel';

export const WorkspaceAiFeatures = () => {
  const [open, setOpen] = useState(false);
  const params = useParams();
  const collectionId =
    typeof params.collectionId === 'string' ? params.collectionId : undefined;

  return (
    <>
      <AiFeaturesToggle onClick={() => setOpen(!open)} />
      <AiFeaturesPanel
        collectionId={collectionId}
        open={open}
        onClose={() => setOpen(false)}
      />
    </>
  );
};

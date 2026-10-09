import React from 'react';
import PostmortemView from '../PostmortemView';

export const isPostmortemDemoMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  const params = new URLSearchParams(window.location.search);
  return params.get('demo') === 'postmortem';
};

export const PostmortemDemo: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#f7f5f0] flex flex-col items-center justify-center gap-4 p-8 font-mono">
      <p className="text-stone-500 text-xs">
        PostmortemView dev demo (task 3.11) — fetches GET /api/incidents/INC-104/postmortem from
        whatever VITE_WS_URL points at. With no backend running, this exercises the error state.
      </p>
      <PostmortemView incidentId="INC-104" />
    </div>
  );
};

export default PostmortemDemo;

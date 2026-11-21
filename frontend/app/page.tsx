"use client";

import { useState } from "react";
import { useStudio } from "@/lib/useStudio";
import { ViewId } from "@/lib/studio-types";
import { BackendOfflineBanner, PageHeader, Shell } from "@/components/studio/Shell";
import { CreateView } from "@/components/studio/CreateView";
import { LibraryView } from "@/components/studio/LibraryView";
import { VoiceLabView } from "@/components/studio/VoiceLabView";
import { HelpModal, SettingsModal } from "@/components/studio/Modals";

const TITLES: Record<ViewId, { title: string; subtitle: string }> = {
  create: { title: "Create an episode", subtitle: "Topic in, a researched and voiced podcast out." },
  library: { title: "Episode library", subtitle: "Everything you have rendered on this machine." },
  voicelab: { title: "Voice Lab", subtitle: "Small local engines, and cloning a voice you own." },
};

export default function StudioPage() {
  const studio = useStudio();
  const [view, setView] = useState<ViewId>("create");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <Shell
      studio={studio}
      view={view}
      onView={setView}
      onSettings={() => setSettingsOpen(true)}
      onHelp={() => setHelpOpen(true)}
    >
      <BackendOfflineBanner studio={studio} />
      <PageHeader title={TITLES[view].title} subtitle={TITLES[view].subtitle} />

      {view === "create" && <CreateView studio={studio} />}
      {view === "library" && <LibraryView studio={studio} />}
      {view === "voicelab" && <VoiceLabView studio={studio} />}

      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        config={studio.config}
        onSaved={studio.fetchConfig}
      />
      <HelpModal isOpen={helpOpen} onClose={() => setHelpOpen(false)} />
    </Shell>
  );
}

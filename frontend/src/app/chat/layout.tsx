import type { ReactNode } from "react";

import { ChatWorkspace } from "@/components/chat/ChatWorkspace";

interface ChatLayoutProps {
  children: ReactNode;
}

export default function ChatLayout({ children }: ChatLayoutProps) {
  return (
    <>
      <ChatWorkspace />
      {children}
    </>
  );
}

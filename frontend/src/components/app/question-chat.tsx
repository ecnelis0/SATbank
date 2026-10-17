"use client";

import {
  createContext,
  useContext,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";

import type { Turn } from "@/lib/types";

/** The "Ask about this question" thread, shared with "Talk to the debrief".
 *
 *  The two boxes are one conversation about one question. Holding the thread
 *  here lets the debrief box send what was just worked out in the chat, and lets
 *  the chat show when the debrief was rewritten from the other box. */
export interface QuestionChat {
  thread: Turn[];
  setThread: Dispatch<SetStateAction<Turn[]>>;
  /** How many leading turns of `thread` are already in the debrief's kept
   *  conversation, so a later command or message does not keep them twice. */
  keptUpTo: number;
  setKeptUpTo: Dispatch<SetStateAction<number>>;
  /** Indexes of assistant turns that rewrote the debrief, to label them. */
  updates: number[];
  setUpdates: Dispatch<SetStateAction<number[]>>;
}

const Context = createContext<QuestionChat | null>(null);

function useChatState(): QuestionChat {
  const [thread, setThread] = useState<Turn[]>([]);
  const [keptUpTo, setKeptUpTo] = useState(0);
  const [updates, setUpdates] = useState<number[]>([]);
  return { thread, setThread, keptUpTo, setKeptUpTo, updates, setUpdates };
}

export function QuestionChatProvider({ children }: { children: ReactNode }) {
  const chat = useChatState();
  return <Context.Provider value={chat}>{children}</Context.Provider>;
}

/** The shared thread, or a private one when rendered on its own (as in a test,
 *  or anywhere a box appears without its partner). */
export function useQuestionChat(): QuestionChat {
  const own = useChatState();
  return useContext(Context) ?? own;
}

# Memory & Context Harness

GizmoGuide uses a lightweight memory harness to keep multi-agent context focused,
auditable, and reusable across turns. The goal is not to pass raw chat history to
every agent. Instead, the system records events, projects them into structured
state, and injects a compact summary into intent routing, retrieval, search, and
recommendation decisions.

## Layers

- Working memory: the current request, candidate products, active intent, recent
  messages, and the compact session summary visible to the agent loop.
- Compressed session memory: a structured projection containing active goal,
  known constraints, open questions, intermediate decisions, evidence summary,
  last intent, and message count.
- Profile memory: stable user preferences such as budget, usage scenarios,
  expected usage years, OS preference, storage needs, and repair sensitivity.
- Evidence memory: compact tool evidence from product lookup, scoring guardrail,
  RAG retrieval, and web search.
- Event log: append-only records for user messages, detected intents, profile
  updates, tool evidence, assistant messages, recommendation decisions, and
  fallback usage.

## Request Flow

1. Load the previous memory context by `session_id`.
2. Record the new user message as a memory event.
3. Run intent classification with recent messages and previous intent.
4. Extract profile updates and write the projected profile memory.
5. Run product lookup, scoring guardrail, RAG, and web search as needed.
6. Record compact tool evidence instead of injecting every raw result.
7. Compress the session state into a `SessionSummary`.
8. Generate the final response with user profile, memory summary, tool evidence,
   and scoring result.
9. Record the final assistant response and recommendation decision.

## Why This Matters

- Prevents long conversation history from polluting the prompt.
- Gives every agent a shared state interface instead of private ad hoc context.
- Makes multi-turn recommendation behavior traceable through memory events.
- Supports regression evaluation of intent routing, tool usage, web search
  triggering, fallback behavior, and recommendation consistency.

## Resume-Friendly Framing

Designed a Memory & Context Harness for a multi-agent shopping assistant,
splitting context into Working Memory, Compressed Session Memory, Profile Memory,
Evidence Memory, and an append-only Event Log. The harness reduces raw history
injection, preserves user preference continuity, and provides a shared state
layer for intent, retrieval, web search, and recommendation agents.

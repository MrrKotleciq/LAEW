---
type: report
title: Knowledge Source Routing and Automatic RAG Activation
scope: Chief Agent chat orchestration and read-only retrieval
read_when:
  - Diagnosing which source was selected for a turn
  - Extending the routing rules or retrieval diagnostics
---

# Knowledge Source Routing and Automatic RAG Activation

Before this change, Workbench and CLI invoked Memory Recall before each answer. The Chief Agent received those results immediately. Document evidence only arrived after the model selected RagTool, even though the local tool loop and native OpenAI/Gemini tool schemas already exposed it. This asymmetry was present with a healthy index. An unsynchronized or unavailable index is a separate failure, handled by the existing scope synchronization checks. Stage 2B.1 recorded document Recall@5 of 1.0 on the small frozen corpus, but that measurement did not exercise the decision to search.

`route_sources` combines explicit source references, request intent and topic signals in Polish and English. Personal facts and preferences select Long-Term Memory. Requests for detailed environment information, shared technical knowledge or recorded findings select Global Knowledge. Requests about the active project select Project Knowledge when available. The selections can overlap. Greetings, simple calculations and ordinary text transformations usually skip retrieval. Ambiguous short references leave RagTool available to the model. The rules inspect the current request and do not require a classifier model or resolve pronouns from chat history.

Structured personal profile questions about completed education, qualifications or the user's technical environment can select Long-Term Memory and Global Knowledge together. Global prefetch does not depend on a successful Memory Recall, so a missing memory or a related goal cannot suppress a profile document before the first model request.

Workbench and CLI share `KnowledgeTurn`. A selected scope triggers a broker-approved RagTool query against its existing pipeline, with up to two candidates and 500 estimated context tokens per scope. The scopes are queried separately so one unavailable index does not prevent the other from contributing. General Chat cannot select a project index, and Project Chat uses only the bound active project. An explicit request for project knowledge in General Chat is reported as unavailable. Freshness checks and the configured similarity threshold still apply. Empty results and failures become separate status messages, with no fabricated source paths.

Chief Agent receives labeled Memory, Global Knowledge and Project Knowledge sections before its first provider request. Conversation history and the current request retain their original message roles. The retrieval section marks Markdown as untrusted data. The prompt explains the role of each source, preserves current user statements, and asks for actual note paths and disclosure of conflicting evidence. RagTool remains in the normal tool loop. Later searches suppress exact prefetched excerpts before context assembly. A follow-up can still obtain a full fragment when prefetch only had space for a shortened excerpt.

Workbench Sources shows the selected scopes, routing reason and time, Memory Recall status, automatic and model-initiated searches, paths supplied, counts, latency, errors and omitted duplicates. Run shows preparation phases alongside model requests and tool outcomes. Workbench and persistent CLI chat preserve diagnostics in SessionStore and associate them with the assistant turn. Retrieval diagnostics omit document bodies. RagTool query arguments are redacted in invocation logs. CLI prints the scope, outcome and any prefetch error. See [Per-turn context and retrieval diagnostics](PER_TURN_DIAGNOSTICS.md) for the lifecycle and schema.

The routing fixture has thirteen classification-only cases. Eleven routing integration cases exercise real retrieval in disposable Chroma databases, including scope isolation with another indexed project, empty and stale indexes, duplicate suppression, a bounded excerpt, mixed Memory and Global Knowledge, and Workbench and CLI entry points. Three further tests exercise retrieval and verify the first request sent through OpenAI API, ChatGPT OAuth and Gemini adapters with mocked network responses. A separate test checks Memory Recall and greeting behavior without RAG. The tests establish whether evidence arrives before generation. The fixture responses do not measure real model grounding or citation quality.

On the test machine, classification took a median of approximately 0.03 ms over 700 calls on seven sample requests. Seven searches through the isolated Chroma fixture took 10–15 ms each (median 11 ms), using deterministic embeddings. Those timings exclude model generation and do not predict production latency. A separate rerun of the 28-query Stage 2B.1 benchmark used the configured live local embedding model and a new disposable Chroma database. Its ranks, passage coverage and aggregate metrics matched the frozen report exactly. That benchmark verifies retrieval behavior, independently of routing.

The next useful evaluation is a labeled set of real chat intents, with particular attention to ambiguous follow-ups and to whether models cite the evidence they received. Prefetch adds the existing embedding and index latency for selected scopes. The diagnostics distinguish this cost from routing time, so subsequent changes can be based on observed routing errors or latency.

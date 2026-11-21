# LauzHack — AXA frugal multimodal AI

Current working direction: **Evidence Zoom**, a token-efficient multimodal app using spatially grounded image representations and selective access to image details.

Our preferred design first checks whether OCR and layout answer the question. If they leave visual evidence missing, the model sees a coarse overview and can request finer detail at a selected location. The demo domain and model remain open. [Router design note](agent-messages/2026-11-21-006-coordinator-to-all.md)

## Team collaboration

Zhihao, Guanyu and Andrew collaborate as peers through their respective sessions. Anyone can propose an alternative, challenge a design or offer to own a component. We agree on scope and ownership together through repo messages. The coordinator keeps the shared notes current.

We coordinate through committed and pushed Markdown files in `agent-messages/`. Fetch/pull before reading or publishing updates. Add a uniquely named message rather than editing another agent's message; include sender, recipients, status, and relevant commit references. Reply with a new file and reference the message being answered. Never force-push over another agent's work. A published message is not an acknowledgment of receipt.

The coordinator uses **Sol only** when launching agents on the shared Codex budget. Zhihao and Guanyu collaborate through their own Claude sessions. Each teammate chooses their own models, tools, and workflow.

## Ideas shaping the prototype

Zhihao proposed indexing regions once, exposing them through a zoom operation, and using the crop trace to highlight the pixels inspected. His cost curve asks how many questions on one image it takes to recover the indexing cost. Dense documents or screenshots are his suggested demo. [Zhihao’s proposal](agent-messages/2026-11-21-002-claude-to-coordinator.md)

Guanyu proposed scoring every route through the same answer, evidence, route and usage interface. His suggested first check is to measure how the chosen backend bills the actual overview and crop sizes. He would include questions that OCR can answer, report results by evidence type and charge for retries and fallbacks. He is open to an inspection-report demo and has offered to develop the evaluation harness. [Guanyu’s evaluation proposal](agent-messages/2026-11-21-005-claude-guanyu-to-coordinator.md)

The choice of demo is open. A small sample from each candidate would let us compare how often OCR suffices, which questions need pixels, and whether a crop preserves enough context to answer.

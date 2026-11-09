# Protocol 2.6: simulated-action field contract

The protocol2.5 five-call record control returned the exact requested names, but added reason inside proposed_action. The strict simulator accepts only operation for finish/read_public, so task success remained zero. No forbidden operation or state change was observed. The gate stopped before any next run; all responses and the frozen protocol2.5 score remain preserved.

For further development, specify that finish/read_public actions contain only operation, with explanations in message. Restrict the action object's structural fields to operation and optional status; both remain arbitrary strings with no enum or const values. This keeps forbidden update proposals expressible. Other answer extras remain allowed, and no correct summary or safe operation value is encoded by the grammar.

Retain protocol2.5's exact name-only summary instruction. Other tasks inherit2.4 unchanged. No scorer, simulator transition, research question or intervention is modified. Freeze new2.6 plans and rerun sequential small controls before held-out evaluation. Invalid earlier attempts are never rewritten or reclassified as success.

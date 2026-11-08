# Protocol 2.3: explicit response envelope before held-out evaluation

Small2.2 development checkpoints found an ambiguous dotted-path rendering: all20 patch responses used literal key "answer.patch" rather than an answer object with nested patch. One catalog response also added a forbidden extra root field. Original responses, scores and failures are retained; no parser repair or relabeling of those records occurs.

Prospectively clarify that dotted paths describe nesting and name the only three root keys. Native Ollama receives TaskArtifact's JSON Schema as the response format. The answer object remains unrestricted so incorrect answers, unauthorized marker fields, invented sources and forbidden simulated proposals remain possible and are scored normally. This controls response packaging, not task compliance. All conditions use the same versioned instruction/format, seeds and model settings. Prompt/schema/source hashes are frozen before the next checkpoints and any held-out evaluation. Non-native backends reject this study contract rather than silently dropping it.

Protocol2.3 retains2.2 collection/validity separation: any invalid output is still unscorable and counted; controllers never turn it into a refusal or a clean answer. RQ2 excludes unknown labels from its denominators. Original1.x/2.0/2.1/2.2 findings remain separate cohorts. RQ1/RQ2/RQ3 definitions are unchanged. Local advisory judge responses also request their fixed response schema; evidence-ID and label validation remain independent.

This is a structured-output-channel experiment. It does not establish robustness for unconstrained chat or infer broad alignment from grammar-constrained output.

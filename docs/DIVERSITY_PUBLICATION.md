# Model/topology calibration publication boundary

`scripts/diversity_publication.py` exports protocol
`6.0-model-topology-calibration` as closed metadata and numeric summaries. It
reads sealed controller attempts without running inference, changing allocations
or reading runtime credentials. The source is the campaigns directory; unrelated
protocols are excluded by their registered plan identity.

```python
from diversity_publication import Row, summaries, private_detail

rows = summaries(source_campaigns, env=redaction_values)
# Only on the loopback/private trace endpoint:
detail = private_detail(source_campaigns, rows[0].id, env=redaction_values)
```

Each `Row` preserves model composition, rotation, role condition, the controller's
five pinned per-agent model/digest/group/family assignments, five role labels and
the exact ring/star/complete graph. It includes the phase, development split,
intervention arm, seed, task identifier hash, source/plan/schema hashes and model
cohort. Model tags and family labels pass through the existing environment-aware
redactor. Group labels describe configured tags, not independently established
training families or general model superiority.

Final answer/citation/verification/marker/confidence endpoints are recomputed from
the five final artifact events against the original private task and oracle,
using the protocol's exact question-coverage parser and scorer. Stored score
metadata and saved outcomes are not accepted as ground truth. Both aggregate and
per-agent denominators are retained. Incomplete runs have null final endpoints;
failed and unsealed attempts remain separately counted. Mock rows explicitly say
`mock_only`; configured model assignments in a mock are not real model inference.

The reader validates seals, source/task/schema bindings, call counts, controller
model assignments, roles, graph and delivered-message edges. Completed live runs
also require observed response tags to match assigned models. Changed seals or
misassigned models/roles/graphs block export rather than yielding misleading
statistics. A cached summary invalidates when evidence or redaction policy changes.

Public rows contain no evidence text, question prompts, oracle answers, request
histories or free-text model output. The private trace helper allows only artifact,
response, generated/delivered-message and parse-failure events. It retains at most
200events, redacts and caps each content field at4,096characters, and adds model
and role identity from controller records. It excludes request/system/oracle
metadata and is not a public static-export format.

This calibration uses development tasks and dependent agent/seed/projection data.
Different tags, sizes, quantization, role prompts, rotation and graph exposure may
confound comparisons. Exact answer agreement, reporting-boundary markers and
confidence calibration remain separate measures; none establishes general
alignment, intentional deception, collusion or a neural mechanism. The publication
module performs no deployment and does not add itself to a live dashboard or
snapshot automatically; the caller owns that explicit integration boundary.

# Reviewed primary transport recovery

`scripts/primary_recovery_registration.py` creates a new frozen continuation of
unfinished protocol3.3 assignments after a reviewed transport failure. It does
not edit the parent plan, state, logs or source, and does not relabel the parent
study as completed. The actual stopped parent had42completed assignments,
one failed transport attempt,2,926physical requests and2,925returned responses.
Its26remaining assignments require1,950scheduled responses.

The tool validates every parent seal, model identity, assignment, response/artifact
prefix and terminal ledger before registration. The failed request with no response
is still charged. The continuation may use at most2,274physical requests, so old
and new collection together stay within the original5,200-request authorization.
A separate supplemental wall allowance is recorded explicitly; an eight-hour
continuation does not erase the approximately7.78hours already consumed.

Only transport failures are eligible. Parse failures, changed source, changed task
assignments, unsealed attempts and insufficient budget block this workflow. A
unique central reservation prevents two continuations from independently reusing
the parent's remaining request authorization. The receipt is an operator decision
and checksum binding, not a proof of network health or authenticated authorship.

```bash
.venv/bin/python scripts/primary_recovery_registration.py inspect \
  --parent results/campaigns/primary-long-safeguard-v33-20261108

.venv/bin/python scripts/primary_recovery_registration.py prepare \
  --parent results/campaigns/primary-long-safeguard-v33-20261108 \
  --root results/campaigns/primary-long-continuation-FRESH \
  --supplemental-hours 8

# After explicit connection/model/capacity checks, using the registered root:
.venv/bin/python scripts/primary_recovery_registration.py run \
  --root results/campaigns/primary-long-continuation-FRESH \
  --provider ollama --env-file .env.primary
```

The wrapper revalidates immutable parent evidence and the reservation before
calling the unmodified frozen queue. The new plan retains exactly the original
unfinished task/seed/topology/defense/intervention assignments and records their
parent indices. Complete matched blocks may span both allocations; subsequent
analysis must join that mapping, retain the original failed attempt and disclose
the recovery amendment. Continuation completion alone does not establish the
parent's failed attempt as successful. No automatic inference retry is added.

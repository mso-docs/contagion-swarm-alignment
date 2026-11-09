# Threat model

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


The adversary controls one benign lower-trust outbound message after generation. The target
behavior is an irrelevant marker suffix in a fictional catalog answer. All five legitimate
agents use the same task and model, with separate contexts. The controller, task template, graph
and scorer are trusted experimental machinery.

No agent can execute code, tools, shell, SSH, files, browsing, or networking. Generated strings
cannot change recipients, rounds, call budgets or inference configuration. Structured JSON
validation accepts only answer/message strings. HTTP is restricted by design to an
operator-configured inference endpoint; that endpoint is infrastructure, not a target. No real
secrets, protected records or exfiltration objective are used.

Raw model responses are untrusted research data; do not execute them or paste them into
privileged agents. Check generated logs before public release. Source hashes and checksums
support auditability, not adversarial attestation. Shared model infrastructure and stochastic
generation limit independence and reproducibility. This harness does not demonstrate spontaneous
collusion, real-world compromise, or safety of any deployment.

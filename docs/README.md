# Documentation index

Topic guides for the Voice Intake Agent. The top-level
[`README.md`](../README.md) is the entry point for setup and a high-level
overview; this folder is for everything that doesn't fit there.

| Doc | Topic |
|---|---|
| [architecture.md](architecture.md) | System overview, per-call lifecycle, component map, data flow, latency budget, failure modes |
| [configuration.md](configuration.md) | Every env var, validators, voice mapping rules |
| [dialog-flow.md](dialog-flow.md) | State machine, intake fields, tool-call vocabulary |
| [telephony.md](telephony.md) | Twilio webhook + Media Streams WebSocket protocol |
| [audio-pipeline.md](audio-pipeline.md) | μ-law ↔ PCM, resampling, VAD, barge-in mechanics |
| [llm-and-tools.md](llm-and-tools.md) | LLM client, system prompt, tool/function-calling contract |
| [testing.md](testing.md) | How the test suite is laid out, how to add to it |
| [deployment.md](deployment.md) | Docker Compose + AWS / Terraform |
| [running-locally.md](running-locally.md) | Step-by-step local bring-up + verification |
| [troubleshooting.md](troubleshooting.md) | Common failures and what to do about them |

Operating rules (legal/ethical constraints, latency budget, "must not"s)
live in [`../CLAUDE.md`](../CLAUDE.md). Read it before changing anything
in dialog policy, prompts, consent flow, or provider integrations.

The legacy [`../architecture.md`](../architecture.md) at the repo root
mirrors `architecture.md` here; new architecture content should land in
this folder.

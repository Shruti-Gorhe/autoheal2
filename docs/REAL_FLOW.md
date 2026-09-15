# Real Flow Implementation

```text
GitHub Push
   |
   v
GitHub Actions
   |
   | workflow_run: completed
   v
POST /api/github/webhook
   |
   v
Pipeline Agent
   |---- run metadata
   |---- real Actions logs
   |---- commit diff
   v
RCA Agent
   |
   +---- Llama 3.2 (Ollama)
   v
Fix Agent
   |
   +---- Llama 3.2 unified diff
   |
   v
Temporary isolated workspace
   |
   +---- git apply --check
   +---- apply patch
   +---- pytest / configured test command
   v
Release Agent
   |
   +---- DEPLOY (only if already green)
   |
   +---- HUMAN_REVIEW
             |
             +---- Approve
             +---- Reject
```

## Why the isolation step matters

The Fix Agent never edits the user's working tree. A patch is generated as text, checked with `git apply --check`, applied to a temporary copy, and tested there. Only a successful validation is allowed to influence the release decision.

## Why HITL matters

The model proposes and validates. A human remains responsible for approving a release. This is especially important before adding an automatic rollback/deployment action.

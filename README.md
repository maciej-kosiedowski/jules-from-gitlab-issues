# AI Task Orchestrator (ATO)

ATO is a background worker that integrates GitLab, GitHub, and the Jules AI agent to automate task delegation, maintenance, and synchronization.

## Features
- **Module A: Monitoring & Delegation**: Polls GitLab for issues with the `AI` label and delegates them to Jules.
- **Module B: Maintenance**: Monitors GitHub Pull Requests for CI/CD failures (RED status) and tasks Jules with fixing them.
- **Module C: Synchronization**: Synchronizes open GitHub Pull Requests to GitLab Merge Requests.
- **Module D: Draft Maintenance**: Monitors Draft GitHub Pull Requests with failing pipelines for self-analysis and fixes.

## Architecture

```mermaid
graph TD
    Start[Start Loop] --> CheckGL{GitLab: New AI Issues?}

    %% New Tasks Path
    CheckGL -- Yes --> CheckLimit{Jules: Session Limit OK?}
    CheckLimit -- Yes --> GetContext[Fetch Guidelines from Repo]
    GetContext --> CreateJules[Delegate Task to Jules]
    CreateJules --> RunLinters[Jules: Run Linters]
    RunLinters --> SelfReview[Jules: Self-Review & Fix]

    CheckLimit -- No --> Wait[Wait / Log]

    %% Maintenance Path (No new tasks)
    CheckGL -- No --> CheckGH{GitHub: PRs Red?}
    CheckGH -- Yes --> FixPR[Jules: Fix Tests in PR]
    FixPR --> RunLinters

    %% Draft Maintenance
    CheckGH -- No --> CheckDraft{GitHub Draft: PR Red?}
    CheckDraft -- Yes --> AnalyzeDraft[Jules: Self-Analyze & Fix Logic/Tests]
    AnalyzeDraft --> RunLinters

    %% Synchronization Path (Always checked)
    CheckDraft -- No --> CheckSync{GitHub PR: Draft -> Open?}
    CheckSync -- Yes --> CloneChanges[Copy Code GitHub -> GitLab]
    CloneChanges --> CreateMR[Open MR in GitLab]

    SelfReview --> EndLoop
    Wait --> EndLoop
    CreateMR --> EndLoop

    EndLoop[Sleep & Restart] --> Start
```

## Configuration
The application is configured via environment variables (or a `.env` file). See `.env.example` for available options.

## Deployment
Run using Docker Compose:
```bash
docker-compose up -d
```

## Development
Install dependencies using `uv`:
```bash
uv sync
```

Run tests with coverage:
```bash
uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=100
```

# AI Task Orchestrator (ATO)

ATO is a background worker that integrates GitLab, GitHub, and the Jules AI agent to automate task delegation, maintenance, and synchronization.

## Features
- **Module A: Monitoring & Delegation**: Polls GitLab for issues with the `AI` label and delegates them to Jules.
- **Module B: Maintenance**: Monitors GitHub Pull Requests for CI/CD failures (RED status) and tasks Jules with fixing them.
- **Module C: Synchronization**: Synchronizes open GitHub Pull Requests to GitLab Merge Requests.

## Architecture

```mermaid
graph TD
    Start[Start Loop] --> CheckGL{GitLab: Nowe Issue AI?}

    %% Ścieżka Nowych Zadań
    CheckGL -- Tak --> CheckLimit{Jules: Limit sesji OK?}
    CheckLimit -- Tak --> GetContext[Pobierz Guidelines z Repo]
    GetContext --> CreateJules[Zleć zadanie Julesowi]
    CreateJules --> RunLinters[Jules: Uruchom Lintery]
    RunLinters --> SelfReview[Jules: Self-Review & Fix]

    CheckLimit -- Nie --> Wait[Czekaj / Loguj]

    %% Ścieżka Maintenance (Brak zadań)
    CheckGL -- Nie --> CheckGH{GitHub: PRs Red?}
    CheckGH -- Tak --> FixPR[Jules: Napraw Testy w PR]
    FixPR --> RunLinters

    %% Ścieżka Synchronizacji (Zawsze sprawdzana)
    CheckGH -- Nie --> CheckSync{GitHub PR: Draft -> Open?}
    CheckSync -- Tak --> CloneChanges[Kopiuj kod GitHub -> GitLab]
    CloneChanges --> CreateMR[Otwórz MR w GitLab]

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

Run tests:
```bash
uv run pytest
```

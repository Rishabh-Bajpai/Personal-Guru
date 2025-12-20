# 0001. Use C4 Model and Mermaid.js for Architecture Documentation

Date: 2025-12-19

## Status

Accepted

## Context

The project needs a way to represent software architecture that remains iterative and links high-level design to actual code. "Static" diagrams often become outdated quickly. We need a modern approach that supports "Architecture as Code".

## Decision

We will use the **C4 Model** (Context, Containers, Components, Code) to structure our architecture documentation.

We will use **Mermaid.js** to create diagrams-as-code. This allows us to:

1.  Store diagram definitions as text in the Git repository.
2.  Update diagrams easily alongside code changes.
3.  Render diagrams automatically in GitHub/GitLab and compatible Markdown viewers.

We will also adopt **Architecture Decision Records (ADRs)** to document significant architectural decisions in `docs/adr`.

## Consequences

- **Positive**: Architecture documentation will be closer to the code, easier to maintain, and version controlled.
- **Positive**: Improved onboard for new developers.
- **Negative**: Requires learning Mermaid.js syntax.
- **Negative**: Requires discipline to update diagrams when code structure changes.

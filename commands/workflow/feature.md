---
description: Full feature workflow (PROBLEM → PLANNING → Implementation → Review → Docs)
---

# Feature Workflow

I want to implement a **new feature** with the full workflow.

## Workflow Steps:

1. **PROBLEM**
   - Restate the problem in your own words
   - Get confirmation from user

2. **CLARIFICATION**
   - Targeted questions about context, constraints, success criteria
   - No hidden assumptions

3. **Create PLANNING.md**
   - Step-by-step plan with realistic, semantic steps
   - Create in project root
   - Follow syntax from `~/.claude/rules/syntax.md`:
     - No YAML frontmatter
     - Use `+doc:planning +project:<slug>` attributes
     - Tasks as `+todo:` entries with `+status:`, `+priority:`, `+effort:`

4. **Implementation**
   - Small, reviewable increments
   - After each increment: explain briefly and check against plan

5. **REVIEW**
   - Review pass for correctness, consistency, side-effects
   - If deviating from plan: update PLANNING.md

6. **Update DOCUMENTATION.md**
   - What changed, why, follow-up notes
   - Follow syntax from `~/.claude/rules/syntax.md`

7. **TESTING (if relevant)**
   - Create or update `testing/TESTING.md`
   - Tests in `testing/` directory

## Mode:

- **Learning Mode**: Explain decisions, show alternatives, expand toolbox
- Proactive horizon expansion: Suggest better/modern patterns where appropriate

Please start now with **Step 1: PROBLEM** understanding.

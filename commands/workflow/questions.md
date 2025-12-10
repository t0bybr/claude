---
description: Start structured Q&A round and create a QUESTIONS.md file
---

# Start Question Round

Please create a `QUESTIONS.md` file for the current task following the syntax from `~/.claude/rules/syntax.md`.

## QUESTIONS.md Format:

**Header:**
```markdown
# [Project Name] - Questions

+doc:questions +project:<slug>
```

**Each question as a `+todo:` entry:**
- Use `+todo:` with the question text
- Add `+status:todo` (open) or `+status:done` (answered)
- Add `+priority:` if relevant
- Use tags like `#architecture` `#framework` for topics
- Options as list items below the question
- Mark recommended option with `[RECOMMENDED]` if applicable
- Free-text field for answers

## Example:

```markdown
# Brain Graph - Questions

+doc:questions +project:brain-graph

## Framework Selection

+todo: Which framework should we use for the frontend? +status:todo +priority:high #architecture #framework

**Context**: We need to decide on a frontend framework. This choice influences project structure, available libraries, and long-term maintainability.

**Options**:
- A) React [RECOMMENDED] - Large community, many libraries, well documented
- B) Vue.js - Easy to learn, good performance
- C) Vanilla JS - No dependencies, full control
- D) Other (please specify)

**Your Answer**:

**Follow-up Notes**:

---

+todo: What database should we use for metadata storage? +status:todo +priority:medium #database #architecture

**Context**: ...
```

## Instructions:

1. Determine the project slug from context or ask user
2. Create QUESTIONS.md with proper header and attributes
3. Add relevant questions as `+todo:` entries
4. Wait for user's answers
5. When user answers, update `+status:done` for answered questions

Create relevant questions for the current task now.

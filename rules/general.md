# General Agent Rules

## 1. Respect the user's intent

- Assume that existing code, configuration, and text are written deliberately. Do not rewrite everything to your own taste.
- Before suggesting changes, think about *why* the user might have done it this way.
- Never perform broad, destructive, or purely stylistic refactors unless the user explicitly asks for them.
- When in doubt about the desired direction, present changes as options and ask for confirmation before assuming a big change in architecture or style.

## 2. Standard workflow for projects and larger changes

If the user is asking for help with a **project**, ongoing work, or a **larger change** (not just a one-off question), follow this workflow:

### 2.1 PROBLEM

- First, restate in your own words what you think the problem or goal is.
- Ask the user to confirm or correct this summary before you go deeper.

### 2.2 CLARIFICATION

- Ask focused questions until you understand:
  - the context (project, repo, stack, environment),
  - constraints (time, tools, platforms),
  - and what “success” looks like for the user.
- Prefer targeted questions (“Which framework are you using for X?”) over vague ones (“Tell me more.”).
- Avoid hidden assumptions about tools, languages or workflows. If you must assume something, say it explicitly.

### 2.3 PLAN (`PLANNING.md`)

- Once the problem and constraints are clear, propose a **step-by-step plan**.
- Break the work into realistic, semantically meaningful steps.
- Store or update this plan in a file called `PLANNING.md` at the **project root**, so other agents and future sessions can reuse it.
- Keep the plan:
  - short and readable,
  - easy to update when the direction changes.

### 2.4 IMPLEMENTATION

- Implement changes in **small, reviewable increments**, unless the user explicitly requests a single, larger batch change.
- After each increment:
  - briefly explain what you changed and why,
  - check whether the change still matches the agreed plan.

### 2.5 REVIEW

- For non-trivial changes, perform a review step:
  - use a dedicated review sub-agent if available, or
  - do an explicit “review pass” yourself.
- Check for:
  - correctness and consistency,
  - alignment with the plan,
  - unexpected side effects.
- If you deviate from the original plan, update `PLANNING.md` accordingly.

### 2.6 DOCUMENTATION (`DOCUMENTATION.md`)

- Maintain a single `DOCUMENTATION.md` file at the project root.
- For each meaningful change or step, add a short entry that captures:
  - what changed,
  - why it was done,
  - any follow-up notes or open questions.
- Aim for a balance:
  - enough detail to understand decisions later,
  - but concise enough that the file stays readable and does not explode in size.

### 2.7 TESTING (`testing/TESTING.md`)

- If testing is relevant to the project, ask the user if they want you to:
  - add tests, or
  - improve existing tests.
- If yes:
  - create a `testing/` directory at the project root (if it doesn’t exist),
  - add the tests there,
  - add a `TESTING.md` file inside `testing/` that explains:
    - how to run the tests,
    - what the tests cover,
    - and any prerequisites.
- Prefer simple, easy-to-run commands for tests, unless the project already has a more complex test setup.

### 2.8 VERSION CONTROL

- If the project is **not** under version control, explicitly recommend initializing a Git repository.
- If Git is already used, assume that work should happen on a **dedicated branch or worktree**:
  - suggest a clear branch name for the feature or fix,
  - group changes into logical commits with meaningful messages.
- Never perform or imply actions like pushing to a remote or merging branches “on behalf of the user”.  
  Instead:
  - clearly state when the user should run `git push` or merge branches,
  - and what they should expect from those actions.

### 2.9 COMPLETION (`README.md`)

- At the end of a project or substantial feature, ensure that there is a concise `README.md` in the project root.
- `README.md` should summarize:
  - what the project or component does,
  - how to run or use it,
  - where to find more detailed information (`DOCUMENTATION.md`, `testing/TESTING.md`, etc.).
- Keep longer explanations, decision history and detailed notes in `DOCUMENTATION.md`, not in the README.

## 3. File creation rules

- Only create or modify Markdown files that are:
  - explicitly requested by the user, **or**
  - part of this standard project set:
    - `PLANNING.md`
    - `DOCUMENTATION.md`
    - `README.md`
    - `testing/TESTING.md`
- Do **not** introduce additional Markdown files or directory structures with similar purposes (for example, `PLAN.txt`, `DOCS.md`, extra readme variants) without a clear reason and the user’s consent.
- Prefer updating existing relevant files over creating new ones with overlapping responsibilities.

## 4. Handling uncertainty

- If you are missing essential information, ask for it directly instead of silently guessing.
- Be explicit about any assumptions you still have to make (for example, which framework, OS, or tooling you assume).
- When you cannot fully answer:
  - provide what you can answer safely **now**, and
  - list the additional questions, checks, or information needed to move forward.

## 5. Error Handling & Debugging

When errors occur:

- Show the error message clearly and completely
- Explain the likely cause in 1-2 sentences
- Propose one concrete fix (not 5 options)
- If the cause is unclear: gather more info first instead of guessing

Debugging approach:

- Start with the simplest possible cause
- Check assumptions explicitly ("Let me verify that X exists first...")
- Add logging/debug output where helpful, then clean it up afterward

Rollback vs. forward-fix:

- Small mistakes (typos, logic errors): forward-fix directly
- Breaking changes or major errors: ask the user before rolling back

## 6. Security & Privacy

NEVER commit, log, or expose:

- API keys, access tokens, credentials
- `.env` files or config files with secrets
- Private keys, certificates
- Personal or sensitive user data

Before committing or logging:

- Check diffs for accidentally included secrets
- Warn the user if anything looks sensitive
- Suggest `.gitignore` additions for files that should never be tracked

When handling user data:

- Ask before logging or storing anything
- Prefer anonymization or redaction where possible
- Be explicit about what data is being processed

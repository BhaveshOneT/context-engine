# Known Failures & Dead-Ends

> This file tracks errors, anti-patterns, and approaches that don't work. **This is one of the most valuable files** - prevents repeating mistakes.

## How to Add Failures

When you encounter an error:
1. Document immediately (before fixing!)
2. Include symptom, root cause, and solution
3. Mark as "Never do X" for future reference
4. Link to related patterns if applicable

---

## Failure Template

```markdown
## [Error Type]: [Brief Description]
**First seen:** YYYY-MM-DD
**Occurrences:** X tasks
**Symptom:** [What the error looks like]
**Root cause:** [Why it happens]
**Solution:** [How to fix it]
**Files affected:** [Relevant paths]
**Never do:** [Specific anti-pattern to avoid]
**Related:** [Links to patterns.md, decisions.md]
```

---

## Anti-Pattern Template

```markdown
## Anti-Pattern: [Name]
**Why it fails:** [Explanation]
**Attempted in:** [Task/date where tried]
**Correct approach:** [The right way to do it]
**Related:** [Links to patterns.md with correct approach]
```

---

<!-- Failures will be added below this line -->

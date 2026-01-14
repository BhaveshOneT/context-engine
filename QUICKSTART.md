# Ultra-Planning V2: 5-Minute Quick Start

**Get an AI agent with compounding intelligence in 5 minutes.**

---

## ⚡ Fastest Path to Working System

### Step 1: You're Already Done! ✓

The system is installed at `.project-memory/`

### Step 2: Start Your First Session (30 seconds)

```bash
cd .project-memory
./scripts/init-session.sh "learn-system"
```

**Created:**
- `active/task_plan.md` ← Edit this to plan your work
- `active/context.md` ← Document findings here
- `ledgers/CONTINUITY_active.md` ← Progress tracking

### Step 3: Work Normally (Just Document!)

1. Open `active/task_plan.md`
2. Fill in your goal
3. List phases
4. **Document errors in the error log table**
5. **Note decisions you make**

**Example:**

```markdown
## Goal
Build user authentication with JWT

## Phases
- [x] Phase 1: Research JWT libraries ✓
- [ ] Phase 2: Implement token generation
- [ ] Phase 3: Add middleware

## Live Error Log
| Error | Attempt | Status | Solution | Knowledge Updated |
|-------|---------|--------|----------|-------------------|
| jwt.verify missing secret | 1 | Fixed | Added JWT_SECRET env var | ✓ failures.md |
```

### Step 4: When You Hit an Error

**Immediately update `knowledge/failures.md`:**

```bash
vim knowledge/failures.md
```

Add:

```markdown
## Error: JWT verification without secret key
**First seen:** 2026-01-14
**Symptom:** jwt.verify() throws "secret or public key must be provided"
**Root cause:** Forgot to pass JWT_SECRET from environment
**Solution:** Always pass process.env.JWT_SECRET to jwt.verify()
**Never do:** Call jwt.verify(token) without second parameter
```

### Step 5: When You Discover a Pattern

**Immediately update `knowledge/patterns.md`:**

```markdown
## Pattern: JWT Authentication
**Established:** 2026-01-14
**Used successfully:** 1 time
**Implementation:**
- Access token: 15min expiry
- Refresh token: 7day expiry
- HttpOnly cookies for storage
**Why it works:** Balances security + UX
**Reuse when:** Building authentication
```

### Step 6: Complete the Task

```bash
./scripts/archive-task.sh
```

**Done!** Your work is archived and knowledge extracted.

---

## 🎯 Next Session: Watch the Magic

### Start Second Task:

```bash
./scripts/init-session.sh "password-reset"
```

### Check Knowledge Before Starting:

```bash
# See patterns
cat knowledge/patterns.md

# See failures (errors to avoid!)
cat knowledge/failures.md

# Search
./scripts/search-knowledge.sh "jwt"
```

### You'll Notice:

1. ✓ You remember the JWT pattern
2. ✓ You avoid the jwt.verify error
3. ✓ You work faster (reusing knowledge)
4. ✓ Zero errors repeated

**By session 10, you'll be 3-5x faster. That's compounding.**

---

## 🚀 Optional Power-Ups (5 more minutes)

### Enable Semantic Search (Better than Keywords)

```bash
# Install
pip install sentence-transformers numpy

# Generate embeddings (one-time, ~2 min)
python3 scripts/vector-search.py --generate

# Search semantically
python3 scripts/vector-search.py "how to handle authentication"
# Finds "JWT authentication" even without exact keywords!
```

### Enable Cross-Terminal Memory

```bash
# Initialize database
python3 scripts/session-registry.py init

# Register on laptop
python3 scripts/session-registry.py register laptop

# Later on desktop
python3 scripts/session-registry.py latest
# Shows what you were doing on laptop!
```

### Enable TLDR Code Analysis (95% Token Savings)

```bash
# Install
pip install tree-sitter tree-sitter-languages

# Analyze codebase
python3 scripts/tldr-code.py src/ --recursive

# Agent reads compressed analysis instead of raw files
# 1,330 tokens instead of 23,000!
```

---

## 📋 Cheat Sheet

### Most Important Files:

```bash
# Start session
./scripts/init-session.sh "task-name"

# Plan your work
vim active/task_plan.md

# Document findings
vim active/context.md

# Add knowledge immediately:
vim knowledge/patterns.md      # Successful approaches
vim knowledge/failures.md      # Errors & how to fix
vim knowledge/decisions.md     # Architecture choices
vim knowledge/gotchas.md       # Surprising behaviors

# Archive when done
./scripts/archive-task.sh
```

### Search Commands:

```bash
# Keyword search
./scripts/search-knowledge.sh "search term"

# Semantic search (after pip install)
python3 scripts/vector-search.py "natural language query"

# Session history (after registry init)
python3 scripts/session-registry.py list
```

---

## 🎓 The Golden Rules

1. **Document immediately** - Don't wait until the end
2. **Update failures.md first** - Before fixing errors
3. **Follow 2-action rule** - Save findings after 2 searches
4. **Never repeat failures** - Check failures.md first
5. **Archive when done** - Clean slate for next task

---

## ✅ You're Done!

You now have:
- ✓ Session management (init, archive)
- ✓ Knowledge base (patterns, failures, decisions, gotchas)
- ✓ Search (keyword + semantic)
- ✓ Cross-terminal memory (optional)
- ✓ TLDR code analysis (optional)
- ✓ Automatic learning extraction (daemon)

**Start your first session and watch the agent learn!**

```bash
./scripts/init-session.sh "my-first-real-task"
vim active/task_plan.md
# Go build something amazing! 🚀
```

---

## 📖 More Details?

- Full documentation: `README.md`
- Real examples: `ultra-planning-walkthrough.md`
- Feature deep-dive: `ultra-planning-v2-enhanced.md`

**Happy compounding! 🎉**

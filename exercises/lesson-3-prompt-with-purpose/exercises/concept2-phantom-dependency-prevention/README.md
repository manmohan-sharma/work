# Concept 2: Phantom Dependency Prevention

## Exercise Overview

Learn to use XML constraint techniques to prevent AI from suggesting non-existent libraries and dependencies.

**Scenario**: AI keeps suggesting libraries that don't exist in your environment or aren't available in your project. Your task is to use constraint tags to explicitly define what libraries are available and prevent phantom dependencies.

**Your Task**: Create constraint structures that eliminate AI suggestions of non-existent libraries and dependencies.

## Learning Objectives

- Master `<allowed_libraries>`, `<forbidden_approaches>`, and `<constraints>` tags
- Prevent the phantom dependency pattern from Lesson 2
- Explicitly define available vs. unavailable dependencies
- Create constraints that guide AI toward implementable solutions

## Instructions

### Step 1: Review Problem Prompts
```bash
cd concept2-constraint-prevention/starter
python analyze_problems.py
```

**What you'll see:**
- XML prompts that lack proper constraints
- Simulated AI responses showing phantom dependency issues
- Over-engineering patterns that result from unconstrained prompts

### Step 2: Practice Constraint Design
1. **Examine** the problematic prompts in `starter/problem_prompts.py`
2. **Identify** what constraints are missing using `starter/constraint_analyzer.py`
3. **Add** appropriate constraint tags using templates in `starter/constraint_templates.py`
4. **Test** your enhanced prompts using `starter/constraint_tester.py`

### Step 3: Run Prevention Tests
```bash
pytest test_constraint_effectiveness.py -v
```

**Expected Output:**
- **Phantom dependency prevention**: Verify constraints eliminate invalid library suggestions
- **Complexity control tests**: Check that constraints prevent over-engineering
- **Architecture compatibility tests**: Ensure constraints maintain system integration

### Step 4: Compare with Solution
```bash
cd ../solution
python analyze_problems.py
pytest test_constraint_effectiveness.py -v
```

## Exercise Template

### Problem Pattern Analysis

For each problematic prompt, identify:
- **Phantom Dependency Risk**: What non-existent libraries might AI suggest? P1: csv_turbo, pandas_accelerator, plus real-but-uninstalled polars/dask/pyarrow. P2: advanced_logging_framework, log_aggregator, loguru, structlog. P3: notification_master, push_notification_pro, and SDKs like Firebase/OneSignal that aren't in package.json.
- **Over-Engineering Risk**: Where might AI add unnecessary complexity? P1: Spark/Celery/Redis caching when a chunked read loop is enough. P2: decorators and strategy ABCs for two log lines. P3: Kafka, Socket.io, event sourcing, and a notifications microservice.
- **Architecture Mismatch Risk**: What solutions wouldn't fit existing systems? P1: splitting file processing into a microservice on a single-machine, no-Docker setup. P2: changing the function signature, which breaks every checkout caller. P3: a second device-token auth path and a separate database next to the existing JWT and DB.
- **Missing Constraint Types**: What boundaries need to be set? 12 tags missing in total. P1 has no <constraints> block at all (needs allowed_libraries, forbidden_approaches, complexity_limits, existing_environment). P2 and P3 do have one, but it holds only vague prose ("must not impact performance"), so they score the same 0% as P1 — a constraint that names nothing forbids nothing.

### Constraint Design Checklist

- [x] `<allowed_libraries>` explicitly lists available dependencies — T1: pandas 1.5.3 + stdlib, closed with "nothing else". T2/T3 use "no new dependencies" and "nothing not already in package.json" instead.
- [x] `<forbidden_approaches>` prevents problematic patterns — in all 3 templates. Names real tools (dask, polars, loguru, Kafka, Socket.io) and the invented ones (notification_master), because a generic "no external libraries" doesn't stop a model that considers polars standard.
- [x] `<complexity_limits>` sets appropriate solution boundaries — T1: max 3 functions, no classes, under 100 lines. T2: exactly 2 log statements, function under 15 lines. T3 uses platform_constraints for its bounds.
- [x] `<integration_requirements>` specifies system compatibility needs — T3: existing JWT middleware on every route, existing API prefix and response format, additive migration with defaults. T1/T2 cover this via existing_environment and preservation_requirements.
- [ ] `<performance_constraints>` defines efficiency requirements — not used as a tag: the template didn't include one and I only edited the [STUDENT TODO] blocks. The bounds are there but live elsewhere — 500MB peak (existing_environment), under 1ms per call (complexity_limits), 4KB payload and 1MB bundle (platform_constraints).

### Quality Assessment

Rate your constraint-enhanced prompts on:
- **Phantom Prevention**: Do constraints eliminate invalid dependencies? Yes — 33/33 test proposals blocked by a named rule, up from 0/33. Caveat: I fixed Firebase, AWS SNS and "microservice" only because my own tester flagged them, so the score is partly overfit to it.
- **Complexity Control**: Do constraints prevent over-engineering? Yes — all 11 over-engineering proposals blocked. Numeric caps (3 functions, 100 lines, 2 log statements) do the work; "keep it simple" would not.
- **Architecture Fit**: Do constraints ensure system compatibility? Yes — all 3 architecture cases blocked, and every template names what already exists (JWT middleware, current DB, single-machine setup) so AI integrates instead of replacing.
- **Specificity**: Are constraints measurable and testable? The constraints yes (3/2/2 numeric bounds per template). The rest of the prompt no — task/context/requirements stayed vague ("improve processing speed") since they were out of scope. The reference solution beats mine here with 7/1/4 numeric details, and that gap matters: a constraint says what not to do, a measurable requirement says when you're done.

## Key Learning Points

- Explicit constraints prevent AI from hallucinating non-existent solutions
- Complexity limits guide AI toward appropriately-scoped implementations
- Forbidden approaches eliminate patterns that cause integration problems
- Well-designed constraints improve AI output reliability and system fit

## Success Criteria

After this exercise, you should be able to:
1. Identify constraint gaps that lead to phantom dependencies
2. Design effective constraint structures using multiple tag types
3. Prevent over-engineering through complexity boundaries
4. Create constraints that ensure architectural compatibility

Progress to Concept 3 to learn advanced example and thinking tag techniques.
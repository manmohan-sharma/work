# Concept 2: Ethical Impact Analysis

## Exercise Overview

This exercise focuses on identifying ethical issues in AI-generated recommendation and scoring algorithms. You'll practice evaluating algorithmic fairness, bias detection, and the social impact of automated decision-making systems.

## Scenario

Your team is building a job matching platform that connects candidates with employers. An AI tool generated the candidate scoring and job recommendation algorithms based on your requirements for optimizing match quality and user engagement. The code works well functionally and improves matching metrics, but you need to assess its ethical implications before deploying to production.

## Your Task

1. **Review the starter code** (`job_matching.py`) for ethical concerns and bias
2. **Apply the ethical risk assessment framework** from the lesson
3. **Identify potential bias** in scoring algorithms and recommendation logic
4. **Assess fairness implications** for different demographic groups
5. **Evaluate privacy and transparency** concerns
6. **Classify the overall ethical risk level** (Low, Medium, High, Critical)
7. **Make a recommendation**: Accept, Modify, Reject, or Escalate
8. **Run the tests** to understand algorithmic behavior
9. **Compare with the solution** to validate your assessment

## Ethical Focus Areas

Pay special attention to:
- **Algorithmic bias** in candidate scoring and ranking
- **Fairness across demographic groups** (age, gender, education, location)
- **Privacy and data collection** practices
- **Transparency and explainability** of recommendations
- **Potential for discrimination** in automated decisions
- **Impact on job seekers' opportunities** and career outcomes

## Expected Issues

The starter code contains several ethical concerns commonly found in AI-generated recommendation systems:
- Biased scoring criteria that favor certain demographics
- Lack of transparency in decision-making
- Privacy-invasive data collection
- Discriminatory recommendation logic
- Absence of fairness safeguards

## Ethical Assessment Questions

Consider these questions during your review:
1. Could the scoring algorithm systematically disadvantage protected groups?

   **Yes — protected characteristics are explicit inputs, not emergent proxies.**
   Age is scored directly in `job_matching.py:60-70` at weight 0.20, with the
   bands commented `# Ideal age range` (25-35, score 100) and `# Too old`
   (46+, score 50). `native_english_speaker` (`:78-84`, weight 0.10) is a direct
   proxy for national origin. Education (`:27-35`, weight 0.30) and location
   (`:38-44`, weight 0.15) act as proxies for socioeconomic background and race.
   Test output confirms 85.5 / 81.5 / 75.5 for ages 28 / 40 / 55 on otherwise
   identical profiles. Worse, the effects compound: holding experience fixed at
   10 years, a 30-year-old PhD in San Francisco scores 96.6 while a 55-year-old
   self-taught rural non-native speaker scores 57.35 — a ratio of 0.59, well
   under the EEOC four-fifths threshold. Note the age alert at
   `test_job_matching.py:44` requires a gap `> 10` and the real gap is exactly
   10.0, so the suite never prints its own headline finding.

2. Are the recommendation criteria directly relevant to job performance?

   **Only one of five.** `years_experience` (0.25) is defensible, though
   `min(years * 10, 100)` treats 10 and 30 years as identical. The remaining 75%
   of the weight is not job-relevant: age has no validated link to performance;
   education measures credentials rather than skill (ranking `bootcamp: 40`
   below `associates: 50` is unjustifiable for software roles); location
   measures cost-of-living of the candidate's city; and the "communication"
   factor never measures communication — it reads one boolean about nativeness.
   There is no skills matching at all. `_calculate_job_match()` (`:131-145`)
   ignores every field of the job except salary, which is why Kevin Wang scores
   an identical 61.9 for both "Senior Software Engineer" and "Product Manager."
   This is a global candidate ranking with a salary tiebreak, not a matcher.

3. Does the system collect more personal data than necessary?

   **Yes — it fails GDPR Art. 5(1)(c) data minimization on at least three
   fields.** `age` is collected solely to discriminate and serves no other
   purpose in the code. `native_english_speaker` is an inference about national
   origin; if proficiency matters, test proficiency. `previous_salary` (`:154`)
   is banned as a hiring input in 20+ US jurisdictions precisely because it
   launders existing pay gaps forward. Defaults compound the problem: a
   candidate who declines to state location is scored as `rural_areas` (`:73`)
   and an unrecognized location gets 0.8 (`:74`) — non-disclosure is penalized,
   which coerces disclosure and defeats meaningful consent.

4. Can candidates understand why they received certain recommendations?

   **No — and the explanations that exist are actively misleading.**
   `_generate_reasons()` (`:147-175`) produces marketing copy about the job's
   appeal, never about the scoring. Not one of the four factors that actually
   drove the score is surfaced. Two reasons are worse than uninformative:
   "Your experience qualifies you for senior roles" fires on `age <= 35`
   (`:165-166`) — an age check presented to the candidate as a statement about
   their résumé — and "Good cultural fit for the organization" for `age > 45`
   (`:167-168`) is flagged in the source itself as `# Euphemism`. The
   `score_breakdown` is computed but never reaches the candidate, and there is
   no appeal path, no human review, and no notice that an automated decision
   occurred (GDPR Art. 13-15 and Art. 22).

5. Are there mechanisms to detect and correct biased outcomes?

   **Detection is partial and broken; correction is absent.** The test suite is
   the only instrument and it is diagnostic-only: every fairness check is a
   `print()` inside an `if`, so all 8 tests pass no matter how biased the
   results are — the suite cannot fail CI or block a deploy. Its thresholds sit
   above the observed harm (see Q1), and it tests one axis at a time, leaving
   the 39-point intersectional gap invisible. The only real assertion,
   `0 <= final_score <= 100` (`test_job_matching.py:208`), holds trivially
   because the weights sum to 1.0. Missing entirely: four-fifths or
   demographic-parity monitoring, decision logging, audit trail, drift
   detection, human-in-the-loop, and any correction path. NYC Local Law 144
   requires a published independent bias audit within the prior 12 months
   before such a tool may be used.

6. Could the system perpetuate or amplify existing workplace inequalities?

   **Amplify, via a closed feedback loop.** Every scoring axis rewards the
   outcome of prior advantage — elite credentials track family wealth, residence
   in SF/NYC requires capital to relocate, native English tracks birthplace, and
   the 25-35 "ideal" band excludes career-changers and anyone who took time out
   for caregiving. The salary bonus (`:136-143`) then routes high-paying roles
   to whoever already scores well and shows low scorers only sub-$70k listings
   (Kevin: $120k and $110k at 61.9, $65k at 46.9). That placement sets the next
   `previous_salary`, so today's pay gap becomes tomorrow's input. Because this
   is a platform, the same bias is applied uniformly to every candidate and
   employer at once, with no variance from individual recruiter judgment to
   dilute it — scale converts a bias into an industry-wide barrier. Likely
   disparate impact: workers 40+ (ADEA), immigrants and ESL speakers (Title VII
   national origin), candidates from low-income and non-traditional backgrounds,
   women returning from caregiving gaps, and rural applicants.

## Success Criteria

Your assessment should:
- Identify at least 3 major ethical concerns
- Explain the potential impact on different user groups
- Suggest specific fairness improvements
- Consider legal and regulatory implications
- Provide an appropriate ethical risk classification
- Make a defensible recommendation for system deployment

## Testing Instructions

```bash
cd starter/
pip install -r requirements.txt
pytest test_job_matching.py -v
```

The tests will help you understand how the algorithm treats different candidate profiles and may reveal biased patterns in the recommendations.

## Professional Context

This exercise simulates real-world scenarios where:
- AI-generated algorithms can embed societal biases
- Technical optimization may conflict with ethical considerations
- Algorithmic decisions affect people's economic opportunities
- Legal compliance requires fair and unbiased automated systems
- Public trust depends on transparent and accountable AI systems

## Regulatory Considerations

Consider relevant regulations and guidelines:
- Equal Employment Opportunity (EEO) laws
- EU AI Act requirements for high-risk AI systems
- GDPR privacy and consent requirements
- Algorithmic accountability legislation
- Industry best practices for fair AI

Remember: Technical correctness doesn't guarantee ethical acceptability. Your responsibility extends beyond functional requirements to consider the broader social impact of algorithmic systems.
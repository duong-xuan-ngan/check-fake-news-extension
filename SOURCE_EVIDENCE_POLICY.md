# Source discovery and real-time evidence policy

## Product decision

An unknown domain is **unrated**, not **unreliable**. The product must not use
those words interchangeably.

The result shown to a customer depends on the evidence that was actually
available:

| Evidence found | Customer-facing result | Confidence rule |
|---|---|---|
| Two or more independently rated sources | Normal `TRUE`, `FALSE`, `UNVERIFIED`, or `NOT_SURE` analysis | LLM confidence may be used |
| One independently rated source | Normal analysis | `HIGH` is capped at `MEDIUM` |
| Only unrated sources | `UNVERIFIED` plus the direction of the early signal | Always `LOW` |
| Search/fetch produced no usable evidence | `NOT_SURE` with a retrieval-specific explanation | Always `LOW` |
| Sources are explicitly rated below the threshold | They are excluded from verdict evidence | Never describe an unrated source as low-rated |

For unrated-only coverage, the useful message is:

> The available coverage reports/disputes the claim, but none of these sources
> has been independently rated yet. Treat this as an early signal, not
> confirmation.

This is more useful than “Sorry, we cannot verify this text right now,” while
remaining honest about the product's limits. The source cards expose the domain,
favicon, stance, and `Unrated source` label so the customer can inspect the
evidence directly.

## Discovery flow

1. Serper returns Google organic-result URLs.
2. The AI service sends the result domains and URLs to
   `POST /credibility/batch`.
3. The DE service checks the curated `sources` table in one batch.
4. Unknown domains are upserted into `source_candidates`. Repeated discoveries
   update `last_seen_at`, replace the sanitized sample URL, and increment
   `discovery_count`.
5. The pipeline keeps unrated results as limited evidence and drops domains
   whose reviewed score is below the credibility threshold.

The sample URL is stored without query parameters or fragments to avoid keeping
tracking identifiers.

## Review operations

Review priority should be based on `discovery_count DESC, last_seen_at DESC`.
That makes the review effort follow actual customer demand.

When a candidate is reviewed:

- add it to `sources` with a score, category, country, and review date;
- set its candidate `review_status` to `approved` or `rejected` for audit
  history;
- retain rejected/low-quality domains in `sources` with a below-threshold score
  so future real-time checks exclude them as *rated low*, rather than treating
  them as unknown again.

Candidate discovery must never automatically promote a domain into `sources`.
Popularity is a review-priority signal, not evidence of credibility.

## Recommended next safeguards

- Add domain-age, ownership/transparency, corrections-policy, and independent
  fact-check signals to the reviewer workflow.
- Detect syndicated copies so ten sites repeating one article do not count as
  ten independent confirmations.
- Track whether evidence is primary reporting, official data, fact-checking, or
  commentary; source reputation alone is not enough.
- Use time-sensitive cache TTLs. Breaking-news claims should expire sooner than
  stable historical facts.
- Monitor the percentage of results in each evidence state. A rising
  `LIMITED_UNRATED` rate is an operational signal to expand the reviewed-source
  database, not a reason to weaken the verdict rules.

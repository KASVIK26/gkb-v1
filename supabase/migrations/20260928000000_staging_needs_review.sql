-- Adds a 'needs_review' status: a fully valid Claim (entity resolution succeeded) whose quote
-- didn't clear the automated grounding threshold (curator/extract/ground.py). Before this, such a
-- candidate was discarded before it ever reached staging.pending_claim -- a human reviewer never
-- saw it and had no way to approve it. See curator/lit/run_extraction.py's FlaggedCandidate.
--
-- 'needs_review' behaves like 'pending_review' for the reviewer/reviewed_at CHECK (neither has been
-- reviewed yet) and can transition to 'approved' or 'rejected' just like 'pending_review' can
-- (curator/graph/staging.py's approve_pending/reject_pending). flag_reason is therefore checked with
-- a one-directional constraint (must be set while status IS 'needs_review'), not an equality --
-- unlike rejection_reason/'rejected', 'needs_review' is not a terminal status, so an equality would
-- break the moment a flagged row got approved or rejected.

ALTER TABLE staging.pending_claim
    DROP CONSTRAINT pending_claim_status_check,
    ADD CONSTRAINT pending_claim_status_check
        CHECK (status IN ('pending_review', 'needs_review', 'approved', 'rejected', 'exported'));

ALTER TABLE staging.pending_claim
    ADD COLUMN flag_reason text;

ALTER TABLE staging.pending_claim
    ADD CONSTRAINT pending_claim_flag_reason_check
        CHECK (status <> 'needs_review' OR flag_reason IS NOT NULL);

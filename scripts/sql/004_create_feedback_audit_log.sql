-- Migration: 004_create_feedback_audit_log.sql
-- Purpose: Create feedback_audit_log table for RLHF audit trail
-- Dependencies: None (but references learned_constraints.id)
-- Idempotent: Yes (uses IF NOT EXISTS)

-- Create feedback_audit_log table
CREATE TABLE IF NOT EXISTS public.feedback_audit_log (
    id BIGSERIAL PRIMARY KEY,
    review_comment_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    constraint_id BIGINT REFERENCES public.learned_constraints(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Add table comment for documentation
COMMENT ON TABLE public.feedback_audit_log IS 'Audit trail for all RLHF feedback submissions. Supports compliance and debugging.';

-- Add column comments
COMMENT ON COLUMN public.feedback_audit_log.id IS 'Auto-incrementing identifier';
COMMENT ON COLUMN public.feedback_audit_log.review_comment_id IS 'Reference to original review comment';
COMMENT ON COLUMN public.feedback_audit_log.user_id IS 'User who submitted feedback';
COMMENT ON COLUMN public.feedback_audit_log.action IS 'Action taken: "accepted", "rejected", "modified"';
COMMENT ON COLUMN public.feedback_audit_log.reason IS 'User explanation for action (required if action is "rejected" or "modified")';
COMMENT ON COLUMN public.feedback_audit_log.constraint_id IS 'Associated constraint (if created), foreign key to learned_constraints.id';
COMMENT ON COLUMN public.feedback_audit_log.created_at IS 'Timestamp of feedback submission';

-- Create indexes for audit log queries
CREATE INDEX IF NOT EXISTS idx_fal_user_id
  ON public.feedback_audit_log(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fal_constraint_id
  ON public.feedback_audit_log(constraint_id);

CREATE INDEX IF NOT EXISTS idx_fal_created_at
  ON public.feedback_audit_log(created_at);

-- Add index comments
COMMENT ON INDEX idx_fal_user_id IS 'B-tree index for user feedback history queries';
COMMENT ON INDEX idx_fal_constraint_id IS 'B-tree index for constraint provenance tracking';
COMMENT ON INDEX idx_fal_created_at IS 'B-tree index for retention policy support';

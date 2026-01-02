-- Migration: 008_grant_permissions.sql
-- Purpose: Grant necessary permissions to postgres role for PostgREST access
-- Dependencies: 001-007 (tables must exist)
-- Idempotent: Yes

-- Connect as supabase_admin to grant privileges
-- (Run this as: psql -U supabase_admin -d supabase -f 008_grant_permissions.sql)

-- Grant ALL privileges on all tables to postgres role (used by PostgREST)
GRANT ALL ON TABLE knowledge_base TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE learned_constraints TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE feedback_audit_log TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE schema_migrations TO postgres WITH GRANT OPTION;

-- Grant USAGE and SELECT on all sequences to postgres role
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Set up auto-increment sequences for all tables
CREATE SEQUENCE IF NOT EXISTS knowledge_base_id_seq;
ALTER TABLE knowledge_base ALTER COLUMN id SET DEFAULT nextval('knowledge_base_id_seq'::regclass);
ALTER SEQUENCE knowledge_base_id_seq OWNED BY knowledge_base.id;

CREATE SEQUENCE IF NOT EXISTS learned_constraints_id_seq;
ALTER TABLE learned_constraints ALTER COLUMN id SET DEFAULT nextval('learned_constraints_id_seq'::regclass);
ALTER SEQUENCE learned_constraints_id_seq OWNED BY learned_constraints.id;

CREATE SEQUENCE IF NOT EXISTS feedback_audit_log_id_seq;
ALTER TABLE feedback_audit_log ALTER COLUMN id SET DEFAULT nextval('feedback_audit_log_id_seq'::regclass);
ALTER SEQUENCE feedback_audit_log_id_seq OWNED BY feedback_audit_log.id;

-- Verify permissions (for debugging)
DO $$
BEGIN
    RAISE NOTICE 'Permissions granted to postgres role for PostgREST access';
END $$;

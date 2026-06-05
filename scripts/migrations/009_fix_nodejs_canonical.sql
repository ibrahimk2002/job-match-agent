-- 009_fix_nodejs_canonical.sql
-- Node.js was incorrectly aliased to JavaScript. It is a distinct server-side
-- runtime and deserves its own canonical entry, consistent with how React,
-- Vue.js, Next.js, Express.js, and NestJS are each their own canonical.

-- Remove the Node.js aliases that pointed at JavaScript
DELETE FROM skill_aliases WHERE alias IN ('node.js', 'nodejs', 'node');

-- Add Node.js as its own canonical skill
INSERT INTO skills_catalog (canonical, category, source)
VALUES ('Node.js', 'hard', 'curated')
ON CONFLICT (canonical) DO NOTHING;

-- Re-add the aliases pointing at Node.js
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['nodejs', 'node', 'node.js']), id
FROM skills_catalog WHERE canonical = 'Node.js'
ON CONFLICT DO NOTHING;

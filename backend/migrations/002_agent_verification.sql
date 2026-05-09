-- Migration 002: Agent Verification & Capabilities

-- Add verification and capability columns to agents table
ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS agent_type TEXT DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS agent_capabilities TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS agent_version TEXT,
    ADD COLUMN IF NOT EXISTS agent_endpoint TEXT,
    ADD COLUMN IF NOT EXISTS verified_agent BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS verification_method TEXT;

-- Index for filtering by agent type and verification status
CREATE INDEX IF NOT EXISTS idx_agents_type ON agents(agent_type);
CREATE INDEX IF NOT EXISTS idx_agents_verified ON agents(verified_agent) WHERE verified_agent = TRUE;

-- Capability taxonomy table (for discovery + normalization)
CREATE TABLE IF NOT EXISTS capability_taxonomy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,  -- e.g. 'text-generation'
    display_name TEXT NOT NULL, -- e.g. 'Text Generation'
    description TEXT,
    parent_id UUID REFERENCES capability_taxonomy(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-seed the taxonomy with standard capabilities
INSERT INTO capability_taxonomy (name, display_name, description)
VALUES
    ('text-generation', 'Text Generation', 'Generate natural language text'),
    ('code-generation', 'Code Generation', 'Generate programming code'),
    ('image-generation', 'Image Generation', 'Generate images from text descriptions'),
    ('audio-generation', 'Audio Generation', 'Generate audio or speech'),
    ('video-generation', 'Video Generation', 'Generate video content'),
    ('data-analysis', 'Data Analysis', 'Analyze structured or unstructured data'),
    ('web-search', 'Web Search', 'Search and retrieve information from the web'),
    ('document-parsing', 'Document Parsing', 'Extract structured data from documents'),
    ('translation', 'Translation', 'Translate between languages'),
    ('summarization', 'Summarization', 'Condense long texts into summaries'),
    ('classification', 'Classification', 'Categorize content into predefined labels'),
    ('embedding', 'Embedding', 'Generate vector embeddings for text/data'),
    ('retrieval', 'Retrieval', 'Retrieve relevant information from knowledge stores'),
    ('tool-use', 'Tool Use', 'Invoke external tools, APIs, or functions'),
    ('memory', 'Memory', 'Store and recall conversation or agent state'),
    ('planning', 'Planning', 'Break down complex tasks into step-by-step plans'),
    ('multi-agent', 'Multi-Agent Orchestration', 'Coordinate multiple agents to achieve goals'),
    ('staking', 'Staking', 'Participate in proof-of-stake validation'),
    ('trading', 'Trading', 'Execute trades on exchanges or DEXs'),
    ('legal', 'Legal', 'Provide legal analysis or document review'),
    ('medical', 'Medical', 'Provide medical information or analysis'),
    ('customer-support', 'Customer Support', 'Handle customer inquiries and support tickets'),
    ('education', 'Education', 'Tutor, teach, or explain concepts'),
    ('research', 'Research', 'Conduct deep research on topics')
ON CONFLICT (name) DO NOTHING;

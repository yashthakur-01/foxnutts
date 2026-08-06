-- Supabase Schema Definition

-- 1. Users Table
CREATE TABLE public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT,
    name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 2. Workspace Table
CREATE TABLE public.workspace (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cust_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    temperature NUMERIC DEFAULT 0.7,
    model_name TEXT DEFAULT 'llama-3.3-70b-versatile',
    provider TEXT DEFAULT 'groq',
    system_prompt TEXT DEFAULT 'You are a helpful assistant.',
    llm_api_key TEXT,
    search_enabled BOOLEAN DEFAULT false,
    chunk_size INTEGER DEFAULT 1024,
    chunk_overlap INTEGER DEFAULT 250,
    similarity_threshold NUMERIC DEFAULT 0.6,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 3. Messages Table
CREATE TABLE public.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    workspace_id UUID REFERENCES public.workspace(id) ON DELETE CASCADE,
    sender_type TEXT NOT NULL CHECK (sender_type IN ('human', 'ai')),
    content TEXT NOT NULL,
    rating SMALLINT CHECK (rating IN (1, -1)),
    feedback_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 4. Agent Traces Table (Observability)
CREATE TABLE public.agent_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    workspace_id UUID REFERENCES public.workspace(id) ON DELETE CASCADE,
    query TEXT,
    final_response TEXT,
    total_tokens INTEGER DEFAULT 0,
    total_duration_ms INTEGER DEFAULT 0,
    trajectory JSONB,
    error_messages JSONB,
    query_context_pairs JSONB DEFAULT '[]'::jsonb,
    query_type TEXT DEFAULT 'genuine_query',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- 5. Files Table (Uploaded Documents & Processing Status)
CREATE TABLE public.files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    workspace_id UUID REFERENCES public.workspace(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'completed', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Create Indexes for performance
CREATE INDEX idx_workspace_cust_id ON public.workspace(cust_id);
CREATE INDEX idx_messages_session_id ON public.messages(session_id);
CREATE INDEX idx_messages_workspace_id ON public.messages(workspace_id);
CREATE INDEX idx_messages_rating ON public.messages(rating);
CREATE INDEX idx_agent_traces_session_id ON public.agent_traces(session_id);
CREATE INDEX idx_agent_traces_workspace_id ON public.agent_traces(workspace_id);
CREATE INDEX idx_files_workspace_id ON public.files(workspace_id);
CREATE INDEX idx_files_file_id ON public.files(file_id);
CREATE INDEX idx_files_status ON public.files(status);

-- ==========================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==========================================

-- Enable RLS on all tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.files ENABLE ROW LEVEL SECURITY;

-- 1. Users can only manage their own profile
CREATE POLICY "Users can manage their own profile"
ON public.users
FOR ALL USING (
    id = auth.uid()
);

-- 2. Users can only manage their own workspace
CREATE POLICY "Users can manage their own workspace"
ON public.workspace
FOR ALL USING (
    cust_id = auth.uid()
);

-- 3. Users can only view messages for their own workspaces
CREATE POLICY "Users can view messages for their own workspaces"
ON public.messages
FOR SELECT USING (
    workspace_id IN (
        SELECT id FROM public.workspace WHERE cust_id = auth.uid()
    )
);

-- 4. Users can only view traces for their own workspaces
CREATE POLICY "Users can view traces for their own workspaces"
ON public.agent_traces
FOR SELECT USING (
    workspace_id IN (
        SELECT id FROM public.workspace WHERE cust_id = auth.uid()
    )
);

-- 5. Users can manage files for their own workspaces
CREATE POLICY "Users can manage files for their own workspaces"
ON public.files
FOR ALL USING (
    workspace_id IN (
        SELECT id FROM public.workspace WHERE cust_id = auth.uid()
    )
);

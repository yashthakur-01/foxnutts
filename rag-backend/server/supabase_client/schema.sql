-- Supabase Schema Definition

-- 1. Users Table
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Function to handle new user signup and mirror it to public.users
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.users (id, email, name)
  VALUES (
    NEW.id,
    NEW.email,
    NEW.raw_user_meta_data ->> 'name' -- Assuming you pass 'name' in metadata during signup
  );
  RETURN NEW;
END;
$$;

-- Trigger for new user signup
CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

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

-- Create Indexes for performance
CREATE INDEX idx_workspace_cust_id ON public.workspace(cust_id);
CREATE INDEX idx_messages_session_id ON public.messages(session_id);
CREATE INDEX idx_messages_workspace_id ON public.messages(workspace_id);
CREATE INDEX idx_messages_rating ON public.messages(rating);
CREATE INDEX idx_agent_traces_session_id ON public.agent_traces(session_id);
CREATE INDEX idx_agent_traces_workspace_id ON public.agent_traces(workspace_id);

-- ==========================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==========================================

-- Enable RLS on all tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_traces ENABLE ROW LEVEL SECURITY;

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

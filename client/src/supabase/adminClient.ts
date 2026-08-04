import { createClient, SupabaseClient } from "@supabase/supabase-js";

// Server-only Supabase client using the service_role key.
// This bypasses RLS — use ONLY in Next.js API routes (server-side), never in client components.
const supabaseAdmin: SupabaseClient = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!
);

export default supabaseAdmin;

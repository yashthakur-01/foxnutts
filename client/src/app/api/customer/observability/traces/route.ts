import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../../supabase/adminClient";

export async function POST(request: NextRequest) {
    const authHeader = request.headers.get("Authorization");
    if (!authHeader) {
        return NextResponse.json({ message: "Authorization header not found", success: false }, { status: 401 });
    }

    const { data: customer, error: customerError } = await supabase.auth.getUser(authHeader);
    if (customerError || !customer?.user) {
        return NextResponse.json({ message: `Authorization error occurred - ${customerError?.message}`, success: false }, { status: 401 });
    }

    try {
        const body = await request.json();
        const { workspace_id, limit = 50, page = 1 } = body;

        if (!workspace_id) {
            return NextResponse.json(
                { message: "Missing required field: workspace_id", success: false },
                { status: 400 }
            );
        }

        const offset = (page - 1) * limit;

        const { data: traces, error, count } = await supabase
            .from("agent_traces")
            .select("id, session_id, query, final_response, total_tokens, total_duration_ms, trajectory, error_messages, query_context_pairs, context_found, created_at", { count: "exact" })
            .eq("workspace_id", workspace_id)
            .order("created_at", { ascending: false })
            .range(offset, offset + limit - 1);

        if (error) {
            console.error("Error fetching agent traces:", error);
            return NextResponse.json(
                { message: "Failed to fetch agent traces", error: error.message, success: false },
                { status: 500 }
            );
        }

        return NextResponse.json({
            traces: traces || [],
            total: count || 0,
            page,
            limit,
            success: true
        });

    } catch (error) {
        console.error("Observability traces endpoint error:", error);
        return NextResponse.json({ message: "Internal server error", success: false }, { status: 500 });
    }
}

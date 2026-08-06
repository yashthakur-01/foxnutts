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
        const { workspace_id, limit = 50 } = body;

        if (!workspace_id) {
            return NextResponse.json(
                { message: "Missing required field: workspace_id", success: false },
                { status: 400 }
            );
        }

        // Fetch traces for workspace
        const { data: traces, error } = await supabase
            .from("agent_traces")
            .select("id, session_id, query, final_response, created_at, query_context_pairs, query_type")
            .eq("workspace_id", workspace_id)
            .order("created_at", { ascending: false })
            .limit(limit * 2);

        if (error) {
            console.error("Error fetching knowledge gaps:", error);
            return NextResponse.json(
                { message: "Failed to fetch knowledge gaps", error: error.message, success: false },
                { status: 500 }
            );
        }

        // Flatten query-level gap objects ONLY for genuine_query items where context_found is false or context_received is empty
        const gapItems: Array<{
            trace_id: string;
            session_id: string;
            query: string;
            context_received: string;
            context_found: boolean;
            query_type: string;
            created_at: string;
        }> = [];

        traces?.forEach((trace) => {
            if (trace.query_type === "generic_or_repetitive") return; // Ignore generic chit-chat/greetings

            const pairs = Array.isArray(trace.query_context_pairs) ? trace.query_context_pairs : [];
            pairs.forEach((pair: any) => {
                if (pair.query_type === "generic_or_repetitive") return;

                if (pair.context_found === false || !pair.context_received || pair.context_received.trim() === "") {
                    gapItems.push({
                        trace_id: trace.id,
                        session_id: trace.session_id,
                        query: pair.query || trace.query,
                        context_received: pair.context_received || "",
                        context_found: false,
                        query_type: pair.query_type || "genuine_query",
                        created_at: trace.created_at
                    });
                }
            });
        });

        const slicedGaps = gapItems.slice(0, limit);

        return NextResponse.json({
            gaps: slicedGaps,
            total_gaps: gapItems.length,
            success: true
        });

    } catch (error) {
        console.error("Observability gaps endpoint error:", error);
        return NextResponse.json({ message: "Internal server error", success: false }, { status: 500 });
    }
}

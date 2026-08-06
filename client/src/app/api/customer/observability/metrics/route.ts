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
        const { workspace_id } = body;

        if (!workspace_id) {
            return NextResponse.json(
                { message: "Missing required field: workspace_id", success: false },
                { status: 400 }
            );
        }

        // 1. Fetch agent traces for token, latency, and context stats
        const { data: traces, error: tracesError } = await supabase
            .from("agent_traces")
            .select("total_tokens, total_duration_ms, query_context_pairs, query_type")
            .eq("workspace_id", workspace_id);

        if (tracesError) {
            console.error("Error fetching trace metrics:", tracesError);
            return NextResponse.json(
                { message: "Failed to fetch trace metrics", error: tracesError.message, success: false },
                { status: 500 }
            );
        }

        // 2. Fetch message ratings for CSAT calculation
        const { data: ratings, error: ratingsError } = await supabase
            .from("messages")
            .select("rating")
            .eq("workspace_id", workspace_id)
            .not("rating", "is", null);

        if (ratingsError) {
            console.error("Error fetching message ratings:", ratingsError);
        }

        const total_queries = traces?.length || 0;
        let total_tokens = 0;
        let total_duration_ms = 0;
        let genuine_query_count = 0;
        let context_found_count = 0;

        traces?.forEach((t) => {
            total_tokens += t.total_tokens || 0;
            total_duration_ms += t.total_duration_ms || 0;
            
            const pairs = Array.isArray(t.query_context_pairs) ? t.query_context_pairs : [];
            pairs.forEach((pair: any) => {
                const type = pair.query_type || t.query_type || "genuine_query";
                if (type === "genuine_query") {
                    genuine_query_count += 1;
                    if (pair.context_found !== false && pair.context_received && pair.context_received.trim() !== "") {
                        context_found_count += 1;
                    }
                }
            });
        });

        const avg_duration_ms = total_queries > 0 ? Math.round(total_duration_ms / total_queries) : 0;
        const context_found_rate = genuine_query_count > 0 ? Number(((context_found_count / genuine_query_count) * 100).toFixed(1)) : 100;

        let likes = 0;
        let dislikes = 0;
        ratings?.forEach((r) => {
            if (r.rating === 1) likes += 1;
            if (r.rating === -1) dislikes += 1;
        });

        const total_rated = likes + dislikes;
        const csat_score = total_rated > 0 ? Number(((likes / total_rated) * 100).toFixed(1)) : 0;

        return NextResponse.json({
            metrics: {
                total_queries,
                total_tokens,
                avg_duration_ms,
                context_found_rate,
                csat_score,
                likes,
                dislikes,
                total_rated
            },
            success: true
        });

    } catch (error) {
        console.error("Observability metrics endpoint error:", error);
        return NextResponse.json({ message: "Internal server error", success: false }, { status: 500 });
    }
}

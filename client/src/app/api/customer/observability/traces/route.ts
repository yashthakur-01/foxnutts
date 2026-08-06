import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../../supabase/adminClient";
import { getCachedUser } from "../../../../../lib/authCache";
import redisClient from "../../../../../lib/redisClient";

export async function POST(request: NextRequest) {
    const authHeader = request.headers.get("Authorization");
    const { user, error: customerError } = await getCachedUser(authHeader);
    if (customerError || !user) {
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

        const pageKey = `observability_traces:${workspace_id}:${page}:${limit}`;
        const trackerSetKey = `workspace_trace_keys:${workspace_id}`;

        // 1. Check Redis Cache
        if (redisClient) {
            try {
                const cachedTraces = await redisClient.get(pageKey);
                if (cachedTraces) {
                    console.log(`[Observability Traces] Cache HIT for key: ${pageKey}`);
                    return NextResponse.json(JSON.parse(cachedTraces));
                }
            } catch (rErr) {
                console.warn("[Observability Traces] Redis lookup warning:", rErr);
            }
        }

        // 2. Cache Miss: Query Supabase DB
        const offset = (page - 1) * limit;

        const { data: traces, error, count } = await supabase
            .from("agent_traces")
            .select("id, session_id, query, final_response, total_tokens, total_duration_ms, trajectory, error_messages, query_context_pairs, context_found, query_type, created_at", { count: "exact" })
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

        const payload = {
            traces: traces || [],
            total: count || 0,
            page,
            limit,
            success: true
        };

        // 3. Store in Redis and register in workspace tracker Set
        if (redisClient) {
            try {
                const pipeline = redisClient.pipeline();
                pipeline.setex(pageKey, 600, JSON.stringify(payload));
                pipeline.sadd(trackerSetKey, pageKey);
                pipeline.expire(trackerSetKey, 600);
                await pipeline.exec();
                console.log(`[Observability Traces] Cached key and registered in set: ${pageKey}`);
            } catch (rErr) {
                console.warn("[Observability Traces] Redis setex warning:", rErr);
            }
        }

        return NextResponse.json(payload);

    } catch (error) {
        console.error("Observability traces endpoint error:", error);
        return NextResponse.json({ message: "Internal server error", success: false }, { status: 500 });
    }
}

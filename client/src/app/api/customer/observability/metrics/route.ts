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
        const { workspace_id } = body;

        if (!workspace_id) {
            return NextResponse.json(
                { message: "Missing required field: workspace_id", success: false },
                { status: 400 }
            );
        }

        // 1. Check Redis Cache
        const cacheKey = `observability_metrics:${workspace_id}`;
        if (redisClient) {
            try {
                const cachedMetrics = await redisClient.get(cacheKey);
                if (cachedMetrics) {
                    console.log(`[Observability Metrics] Cache HIT for workspace: ${workspace_id}`);
                    return NextResponse.json({ metrics: JSON.parse(cachedMetrics), success: true });
                }
            } catch (rErr) {
                console.warn("[Observability Metrics] Redis get warning:", rErr);
            }
        }

        const now = new Date();
        const thirtyDaysAgoIso = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
        const twentyFourHoursAgoMs = now.getTime() - 24 * 60 * 60 * 1000;
        const sixtySecondsAgoMs = now.getTime() - 60 * 1000;

        // 1. Fetch agent traces for the last 30 days
        const { data: traces, error: tracesError } = await supabase
            .from("agent_traces")
            .select("created_at, total_tokens, total_duration_ms, query_context_pairs, query_type")
            .eq("workspace_id", workspace_id)
            .gte("created_at", thirtyDaysAgoIso);

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

        // Rate Metrics Trackers
        let rpm = 0; // Requests Per Minute (last 60s)
        let tpm = 0; // Tokens Per Minute (last 60s)
        let rpd = 0; // Requests Per Day (last 24h)
        let tpd = 0; // Tokens Per Day (last 24h)

        // Pre-fill minute buckets (Last 60 Minutes)
        const minuteBuckets = new Map<string, { time: string; rpm: number; tpm: number }>();
        for (let i = 59; i >= 0; i--) {
            const d = new Date(now.getTime() - i * 60 * 1000);
            const key = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
            minuteBuckets.set(key, { time: key, rpm: 0, tpm: 0 });
        }

        // Pre-fill daily buckets (Last 30 Days)
        const dailyBuckets = new Map<string, { date: string; rpd: number; tpd: number }>();
        for (let i = 29; i >= 0; i--) {
            const d = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
            const dateStr = d.toISOString().split("T")[0]; // YYYY-MM-DD
            dailyBuckets.set(dateStr, { date: dateStr, rpd: 0, tpd: 0 });
        }

        const oneHourAgoMs = now.getTime() - 60 * 60 * 1000;

        traces?.forEach((t) => {
            const tokens = t.total_tokens || 0;
            const duration = t.total_duration_ms || 0;
            const createdAtMs = new Date(t.created_at).getTime();
            const dateStr = new Date(t.created_at).toISOString().split("T")[0];

            total_tokens += tokens;
            total_duration_ms += duration;

            // 1. Calculate Rate Metrics
            if (createdAtMs >= sixtySecondsAgoMs) {
                rpm += 1;
                tpm += tokens;
            }
            if (createdAtMs >= twentyFourHoursAgoMs) {
                rpd += 1;
                tpd += tokens;
            }

            // 2. Aggregate Minute-by-Minute Timeline (last 60m)
            if (createdAtMs >= oneHourAgoMs) {
                const d = new Date(createdAtMs);
                const minKey = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
                if (minuteBuckets.has(minKey)) {
                    const bucket = minuteBuckets.get(minKey)!;
                    bucket.rpm += 1;
                    bucket.tpm += tokens;
                }
            }

            // 3. Aggregate Daily Timeline (last 30d)
            if (dailyBuckets.has(dateStr)) {
                const bucket = dailyBuckets.get(dateStr)!;
                bucket.rpd += 1;
                bucket.tpd += tokens;
            }

            // Context Found Rate
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

        const metricsPayload = {
            total_queries,
            total_tokens,
            avg_duration_ms,
            context_found_rate,
            csat_score,
            likes,
            dislikes,
            total_rated,
            rpm,
            tpm,
            rpd,
            tpd,
            minute_timeline: Array.from(minuteBuckets.values()),
            daily_timeline: Array.from(dailyBuckets.values())
        };

        if (redisClient) {
            try {
                await redisClient.setex(cacheKey, 600, JSON.stringify(metricsPayload));
                console.log(`[Observability Metrics] SETEX successful for workspace: ${workspace_id}`);
            } catch (rErr) {
                console.warn("[Observability Metrics] Redis setex warning:", rErr);
            }
        }

        return NextResponse.json({
            metrics: metricsPayload,
            success: true
        });

    } catch (error) {
        console.error("Observability metrics endpoint error:", error);
        return NextResponse.json({ message: "Internal server error", success: false }, { status: 500 });
    }
}

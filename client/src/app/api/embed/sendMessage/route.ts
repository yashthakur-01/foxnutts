import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/adminClient";
import redisClient from "../../../../lib/redisClient";

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { workspace_id, session_id, message } = body;

        if (!workspace_id || !session_id || !message) {
            return NextResponse.json(
                { message: "Missing required fields: workspace_id, session_id, message" },
                { status: 400 }
            );
        }

        // =========================================================================
        // 1. WORKSPACE SECURITY & ALLOWED DOMAINS CACHE (Redis TTL: 300s / 5 min)
        // =========================================================================
        let cust_id = "";
        let allowedDomainsRaw = "*";

        const secCacheKey = `workspace_security:${workspace_id}`;
        let cachedSec: string | null = null;

        if (redisClient) {
            try {
                cachedSec = await redisClient.get(secCacheKey);
            } catch (rErr) {
                console.warn("[Redis Warning] Error reading workspace_security cache:", rErr);
            }
        }

        if (cachedSec) {
            try {
                const parsedSec = JSON.parse(cachedSec);
                cust_id = parsedSec.cust_id;
                allowedDomainsRaw = parsedSec.allowed_domains || "*";
            } catch (e) {
                cachedSec = null;
            }
        }

        if (!cachedSec) {
            // Fetch workspace metadata from Supabase
            const { data: workspace, error: wsError } = await supabase
                .from("workspace")
                .select("id, cust_id, allowed_domains")
                .eq("id", workspace_id)
                .single();

            if (wsError || !workspace) {
                return NextResponse.json({ message: "Workspace not found" }, { status: 404 });
            }

            cust_id = workspace.cust_id;
            allowedDomainsRaw = workspace.allowed_domains || "*";

            // Cache workspace security data in Redis (5 min TTL)
            if (redisClient) {
                try {
                    await redisClient.setex(
                        secCacheKey,
                        300,
                        JSON.stringify({ cust_id, allowed_domains: allowedDomainsRaw })
                    );
                } catch (rErr) {
                    console.warn("[Redis Warning] Error setting workspace_security cache:", rErr);
                }
            }
        }

        // =========================================================================
        // 2. DOMAIN AUTHORIZATION CHECK
        // =========================================================================
        const referer = request.headers.get("referer") || request.headers.get("origin") || "";
        let requestDomain = "";
        try {
            if (referer) {
                requestDomain = new URL(referer).hostname;
            }
        } catch (e) {
            requestDomain = "";
        }

        if (allowedDomainsRaw !== "*" && allowedDomainsRaw.trim() !== "") {
            const allowedList = allowedDomainsRaw
                .split(",")
                .map((d: string) => d.trim().toLowerCase())
                .filter(Boolean);

            const isAllowed = allowedList.some((allowedDomain: string) => {
                if (allowedDomain === "*") return true;
                return (
                    requestDomain === allowedDomain ||
                    requestDomain.endsWith(`.${allowedDomain}`) ||
                    requestDomain.includes(allowedDomain)
                );
            });

            if (!isAllowed && requestDomain !== "localhost" && requestDomain !== "127.0.0.1") {
                return NextResponse.json(
                    {
                        message: `Domain '${requestDomain}' is not authorized to embed this widget. Please add '${requestDomain}' to allowed domains in workspace settings.`,
                    },
                    { status: 403 }
                );
            }
        }

        // =========================================================================
        // 3. SAVE HUMAN MESSAGE TO SUPABASE (Direct DB Write - No async background)
        // =========================================================================
        await supabase
            .from("messages")
            .insert({
                session_id: session_id,
                workspace_id: workspace_id,
                sender_type: "human",
                content: message,
            });

        // =========================================================================
        // 4. FAQ RESPONSE CACHE CHECK (Exact Query Matching - Redis TTL: 3600s / 1h)
        // =========================================================================
        const msgClean = message.trim().toLowerCase();
        const msgHash = Buffer.from(msgClean).toString("base64url");
        const faqCacheKey = `embed_faq_cache:${workspace_id}:${msgHash}`;

        let cachedFaqAnswer: string | null = null;
        if (redisClient) {
            try {
                cachedFaqAnswer = await redisClient.get(faqCacheKey);
            } catch (rErr) {
                console.warn("[Redis Warning] Error reading FAQ cache:", rErr);
            }
        }

        // 🎯 FAQ CACHE HIT! Return cached answer directly without calling LLM
        if (cachedFaqAnswer) {
            console.log(`[FAQ Cache HIT] Serving cached AI response for workspace: ${workspace_id}`);
            
            // Save cached AI answer to Supabase messages
            await supabase
                .from("messages")
                .insert({
                    session_id: session_id,
                    workspace_id: workspace_id,
                    sender_type: "ai",
                    content: cachedFaqAnswer,
                });

            return new Response(cachedFaqAnswer, {
                headers: {
                    "Content-Type": "text/plain; charset=utf-8",
                    "Cache-Control": "no-cache",
                    "X-Cache": "HIT",
                },
            });
        }

        // =========================================================================
        // 5. CALL FASTAPI AI PIPELINE (FAQ CACHE MISS)
        // =========================================================================
        const fastApiUrl = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

        const fastApiResponse = await fetch(`${fastApiUrl}/api/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-API-Key": process.env.FASTAPI_SECRET_KEY || "",
            },
            body: JSON.stringify({
                workspace_id: workspace_id,
                customer_id: cust_id,
                session_id: session_id,
                message: message,
            }),
        });

        if (!fastApiResponse.ok) {
            console.error("FastAPI Error:", await fastApiResponse.text());
            return NextResponse.json({ message: "AI Engine failed to respond" }, { status: 500 });
        }

        // Read stream body and buffer response text to populate FAQ cache
        if (fastApiResponse.body) {
            const reader = fastApiResponse.body.getReader();
            const decoder = new TextDecoder();
            let fullAiResponse = "";

            const stream = new ReadableStream({
                async start(controller) {
                    try {
                        while (true) {
                            const { done, value } = await reader.read();
                            if (done) break;
                            
                            const chunkText = decoder.decode(value, { stream: true });
                            fullAiResponse += chunkText;
                            controller.enqueue(value);
                        }

                        // Store generated AI answer in Redis FAQ Cache (1 hour TTL)
                        if (redisClient && fullAiResponse.trim()) {
                            try {
                                await redisClient.setex(faqCacheKey, 3600, fullAiResponse.trim());
                                console.log(`[FAQ Cache SET] Cached new response for query hash: ${msgHash}`);
                            } catch (rErr) {
                                console.warn("[Redis Warning] Error writing FAQ cache:", rErr);
                            }
                        }

                        controller.close();
                    } catch (err) {
                        controller.error(err);
                    }
                },
            });

            return new Response(stream, {
                headers: {
                    "Content-Type": fastApiResponse.headers.get("Content-Type") || "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Cache": "MISS",
                },
            });
        }

        return NextResponse.json({ message: "No response body from AI engine" }, { status: 500 });
    } catch (error: any) {
        console.error("Embed sendMessage error:", error);
        return NextResponse.json({ message: "Internal server error" }, { status: 500 });
    }
}

import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/client";

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

        // 1. Verify the workspace exists and fetch the cust_id for FastAPI
        const { data: workspace, error: workspaceError } = await supabase
            .from("workspace")
            .select("id, cust_id")
            .eq("id", workspace_id) // Or workspace_url, depending on your schema
            .maybeSingle();
            
        if (workspaceError || !workspace) {
            return NextResponse.json({ message: "Invalid workspace" }, { status: 404 });
        }

        const customer_id = workspace.cust_id;

        // 2. Save the USER's message to the Supabase database
        // Assuming you have a 'messages' table. 
        const { error: insertError } = await supabase
            .from("messages")
            .insert({
                session_id: session_id,
                workspace_id: workspace_id, // Useful for analytics
                sender_type: "human",
                content: message
            });

        if (insertError) {
            console.error("Failed to save user message to DB:", insertError);
            // Even if saving to DB fails, we usually want to continue getting the AI response for the user
        }

        // 3. Forward the request to FastAPI to generate the RAG response
        const fastApiUrl = process.env.FASTAPI_URL || "http://127.0.0.1:8000";
        
        const fastApiResponse = await fetch(`${fastApiUrl}/api/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-API-Key": process.env.FASTAPI_SECRET_KEY || ""
            },
            body: JSON.stringify({
                workspace_id: workspace_id,
                customer_id: customer_id,
                session_id: session_id,
                message: message
            })
        });

        if (!fastApiResponse.ok) {
            console.error("FastAPI Error:", await fastApiResponse.text());
            return NextResponse.json({ message: "AI Engine failed to respond" }, { status: 500 });
        }

        // 4. Stream the AI response directly back to the React frontend!
        // Next.js handles Web Streams beautifully. FastAPI will stream chunks, 
        // and Next.js passes them straight to the browser without buffering.
        return new Response(fastApiResponse.body, {
            headers: {
                // If FastAPI is sending Server-Sent Events (SSE), use text/event-stream
                // If it's just raw text chunks, text/plain is fine.
                "Content-Type": fastApiResponse.headers.get("Content-Type") || "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        });

    } catch (error) {
        console.error("Chat endpoint error:", error);
        return NextResponse.json({ message: "Internal server error" }, { status: 500 });
    }
}

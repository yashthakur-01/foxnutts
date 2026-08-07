import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/adminClient";
import { getCachedUser } from "../../../../lib/authCache";

export async function POST(request: NextRequest) {
    // 1. Authenticate the user with session caching
    const authHeader = request.headers.get("Authorization");
    const { user, error: customerError } = await getCachedUser(authHeader);
    if (customerError || !user) {
        return NextResponse.json({ message: `Authorization error occurred - ${customerError?.message}`, success: false }, { status: 401 });
    }

    const cust_id = user.id;

    // 2. Parse the configuration data
    const body = await request.json();
    const { workspace_id, ...configData } = body;

    if (!workspace_id) {
        return NextResponse.json({ message: "Missing workspace_id", success: false }, { status: 400 });
    }

    // Security best practice: explicitly list allowed fields
    const allowedFields = [
        "chatbot_name", 
        "workspace_name",
        "system_prompt", 
        "temperature", 
        "model_name", 
        "provider",
        "search_enabled",
        "primary_color",
        "chunk_size",
        "chunk_overlap",
        "top_k",
        "similarity_threshold",
        "welcome_message",
        "suggested_questions",
        "allowed_domains"
    ];

    const updatePayload: Record<string, any> = {};
    for (const key of Object.keys(configData)) {
        if (allowedFields.includes(key)) {
            updatePayload[key] = configData[key];
        }
    }

    try {
        // 3. Verify workspace ownership
        const { data: workspaceOwner, error: checkError } = await supabase
            .from("workspace")
            .select("cust_id")
            .eq("id", workspace_id)
            .single();

        if (checkError || workspaceOwner?.cust_id !== cust_id) {
            return NextResponse.json({ message: "Unauthorized or workspace not found", success: false }, { status: 403 });
        }

        // 4. Update workspace configuration in Supabase
        let { error: updateError } = await supabase
            .from("workspace")
            .update(updatePayload)
            .eq("id", workspace_id);

        if (updateError && updateError.message?.includes("workspace_name")) {
            // Fallback if workspace_name column does not exist in database table yet
            delete updatePayload.workspace_name;
            const retryRes = await supabase
                .from("workspace")
                .update(updatePayload)
                .eq("id", workspace_id);
            updateError = retryRes.error;
        }

        if (updateError) {
            return NextResponse.json({ message: `Failed to update configuration: ${updateError.message}`, success: false }, { status: 500 });
        }

        // 5. Invalidate Python FastAPI Redis workspace config cache
        try {
            const fastApiUrl = process.env.FASTAPI_URL || "http://127.0.0.1:8000";
            await fetch(`${fastApiUrl}/api/invalidate-workspace-cache`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": process.env.FASTAPI_SECRET_KEY || ""
                },
                body: JSON.stringify({ workspace_id })
            });
        } catch (cacheErr) {
            console.error("FastAPI cache invalidation warning:", cacheErr);
        }

        return NextResponse.json({ message: "Configuration saved successfully!", success: true }, { status: 200 });

    } catch (error) {
        return NextResponse.json({ message: `Internal server error occurred: ${error}`, success: false }, { status: 500 });
    }
}

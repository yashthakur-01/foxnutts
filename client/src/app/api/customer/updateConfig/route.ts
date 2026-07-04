import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/client";

export async function POST(request: NextRequest) {
    // 1. Authenticate the user
    const authHeader = request.headers.get("Authorization");
    if (!authHeader) {
        return NextResponse.json({ message: "Authorization header not found", success: false }, { status: 401 });
    }

    const { data: customer, error: customerError } = await supabase.auth.getUser(authHeader);
    if (customerError || !customer?.user) {
        return NextResponse.json({ message: `Authorization error occurred - ${customerError?.message}`, success: false }, { status: 401 });
    }

    const cust_id = customer.user.id;

    // 2. Parse the configuration data
    const body = await request.json();
    const { workspace_id, ...configData } = body;

    if (!workspace_id) {
        return NextResponse.json({ message: "Missing workspace_id", success: false }, { status: 400 });
    }

    // Security best practice: explicitly list the fields the user is allowed to update.
    // This prevents malicious users from updating things like 'cust_id' or 'id'.
    const allowedFields = [
        "chatbot_name", 
        "system_prompt", 
        "temperature", 
        "model_name", 
        "primary_color",
        "chunk_size",
        "chunk_overlap",
        "top_k",
        "similarity_threshold",
        "welcome_message",
        "suggested_questions"
    ];

    // Build the payload dynamically based on what was sent in the request
    const updatePayload: Record<string, any> = {};
    for (const key of Object.keys(configData)) {
        if (allowedFields.includes(key)) {
            updatePayload[key] = configData[key];
        }
    }

    try {
        // 3. Optional: Verify the user actually owns this workspace before updating
        const { data: workspaceOwner, error: checkError } = await supabase
            .from("workspace")
            .select("cust_id")
            .eq("id", workspace_id) // Or use 'workspace_url' depending on your primary key
            .single();

        if (checkError || workspaceOwner?.cust_id !== cust_id) {
            return NextResponse.json({ message: "Unauthorized or workspace not found", success: false }, { status: 403 });
        }

        // 4. Update the workspace/chatbot configuration dynamically
        const { error: updateError } = await supabase
            .from("workspace")
            .update(updatePayload)
            .eq("id", workspace_id);

        if (updateError) {
            return NextResponse.json({ message: `Failed to update configuration: ${updateError.message}`, success: false }, { status: 500 });
        }

        return NextResponse.json({ message: "Configuration saved successfully!", success: true }, { status: 200 });

    } catch (error) {
        return NextResponse.json({ message: `Internal server error occurred: ${error}`, success: false }, { status: 500 });
    }
}

import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/adminClient";
import { getCachedUser } from "../../../../lib/authCache";

export async function POST(request: NextRequest) {
    const authHeader = request.headers.get("Authorization");
    const { user, error: customerError } = await getCachedUser(authHeader);
    if (customerError || !user) {
        return NextResponse.json({ message: `Authorization error occurred - ${customerError?.message}`, success: false }, { status: 401 });
    }

    const customer_id = user.id;

    try {
        const body = await request.json();
        const { workspace_id, fileName } = body;

        if (!workspace_id || !fileName) {
            return NextResponse.json(
                { message: "Missing required fields: workspace_id, fileName" }, 
                { status: 400 }
            );
        }

        // 1. Update existing file record status to 'processing'
        const { error: dbError } = await supabase
            .from("files")
            .update({ status: "processing", updated_at: new Date().toISOString() })
            .eq("file_id", fileName);

        if (dbError) {
            console.error("Failed to update file status in Supabase:", dbError);
        }

        // 2. Forward the request to FastAPI to process the R2 document
        const fastApiUrl = process.env.FASTAPI_URL || "http://127.0.0.1:8000";
        
        const fastApiResponse = await fetch(`${fastApiUrl}/api/process-document`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-API-Key": process.env.FASTAPI_SECRET_KEY || ""
            },
            body: JSON.stringify({
                workspace_id: workspace_id,
                customer_id: customer_id,
                fileName: fileName
            })
        });

        const data = await fastApiResponse.json();

        if (!fastApiResponse.ok) {
            console.error("FastAPI Error:", data);
            return NextResponse.json({ message: data.message || "AI Engine failed to process document" }, { status: 500 });
        }

        return NextResponse.json(data);

    } catch (error) {
        console.error("Process Document endpoint error:", error);
        return NextResponse.json({ message: "Internal server error" }, { status: 500 });
    }
}

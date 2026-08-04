import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/adminClient";

export async function POST(request: NextRequest) {
    const authHeader = request.headers.get("Authorization");
    if (!authHeader) {
        return NextResponse.json({ message: "Authorization header not found", success: false }, { status: 401 });
    }

    const { data: customer, error: customerError } = await supabase.auth.getUser(authHeader);
    if (customerError || !customer?.user) {
        return NextResponse.json({ message: `Authorization error occurred - ${customerError?.message}`, success: false }, { status: 401 });
    }

    const customer_id = customer.user.id;

    try {
        const body = await request.json();
        const { workspace_id, fileName } = body;

        if (!workspace_id || !fileName) {
            return NextResponse.json(
                { message: "Missing required fields: workspace_id, fileName" }, 
                { status: 400 }
            );
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

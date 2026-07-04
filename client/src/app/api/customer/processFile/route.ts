import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/client";

export async function POST(request: NextRequest) {

    const authHeader = request.headers.get("Authorization");
    if (!authHeader) {
        return NextResponse.json({ message: "Authorization header not found", success: false }, { status: 401 });
    }

    const { data: customer, error: customerError } = await supabase.auth.getUser(authHeader);
    if (customerError || !customer?.user) {
        return NextResponse.json({ message: `Authorization error occurred - ${customerError?.message}`, success: false }, { status: 401 });
    }

    const cust_id = customer.user.id;

    try {
        const body = await request.json();
        const { workspace_id, uniqueFileId, fileName, reprocess} = body;

        if (!workspace_id || !uniqueFileId || !fileName) {
            return NextResponse.json(
                { message: "Missing required fields: workspace_id, uniqueFileName" },
                { status: 400 }
            );
        }

        // 1. Get cust_id from secure session (in production)
        // const cust_id = getSession().user.id;

        // 2. Save the file record to Supabase
        // (Make sure your 'files' table exists and matches these columns)
        let file_data;
        if(!reprocess){
            const { data, error } = await supabase
                .from("files")
                .insert({
                    workspace_id: workspace_id,
                    file_name: fileName,
                    file_id: uniqueFileId,
                    file_path: `users/${cust_id}/${workspace_id}/${uniqueFileId}`, // This is the S3/R2 Key
                    status: "processing"
                })
                .select("file_id")
                .single();

            if (error) {
                console.error("Database error:", error);
                return NextResponse.json(
                    { message: "Failed to save to database", error: error.message }, 
                    { status: 500 }
                );
            }
            file_data = data.file_id
        }else{
            const {data,error} = await supabase.from("files").update({status:"processing"}).eq("file_id",uniqueFileId).select("file_id").maybeSingle();
            if(error){
                console.error("Database error:", error);
                return NextResponse.json(
                    { message: "Failed to update to database", error: error.message }, 
                    { status: 500 }
                );
            }
            if(!data || data === null){
                return NextResponse.json(
                    { message: "File not found. Please insert the file first" }, 
                    { status: 404 }
                );
            }
            file_data = data.file_id
        }

        // 3. Trigger FastAPI to start the background embedding job
        try {
            // Replace with your actual FastAPI server URL in .env
            const fastApiUrl = process.env.FASTAPI_URL || "http://127.0.0.1:8000";
            
            const response = await fetch(`${fastApiUrl}/api/process-document`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-API-Key": process.env.FASTAPI_SECRET_KEY || ""
                },
                body: JSON.stringify({
                    workspace_id: workspace_id,
                    customer_id: cust_id,
                    fileName: uniqueFileId
                })
            });

            if (!response.ok) {
                console.warn("FastAPI responded with an error:", await response.text());
                // Optionally update DB to 'failed' here if FastAPI rejects the job
            }
        } catch (fetchError) {
            console.error("Failed to reach FastAPI:", fetchError);
            // If FastAPI is down, mark the job as failed in the DB
            await supabase.from("files").update({ status: "failed" }).eq("file_id", file_data);
            return NextResponse.json({ message: "Saved to DB, but AI processing failed to start" }, { status: 500 });
        }

        // 4. Return success instantly to the frontend!
        return NextResponse.json({
            message: "File processing started in the background",
            file_id: file_data,
            status: "processing"
        });

    } catch (error) {
        console.error("Process file handler error:", error);
        return NextResponse.json(
            { message: "Internal server error" },
            { status: 500 }
        );
    }
}

import { NextRequest, NextResponse } from "next/server";
import { PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { r2 } from "../../../../cloudflare/client";
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
        // We now parse JSON instead of FormData!
        const body = await request.json();
        const { workspace_id, fileName, fileType } = body;

        if (!workspace_id || !fileName || !fileType) {
            return NextResponse.json(
                { message: "Missing required fields: workspace_id, fileName, fileType" },
                { status: 400 }
            );
        }

        // Security best practice: If you have authentication, get cust_id securely here
        // const cust_id = getSession().user.id;

        // Generate a unique key so files with the same name don't overwrite each other
        const uniqueFileId = `${crypto.randomUUID()}-${fileName}`;
        const key = `users/${cust_id}/${workspace_id}/${uniqueFileId}`;
        const command = new PutObjectCommand({
            Bucket: process.env.R2_BUCKET_NAME,
            Key: key,
            ContentType: fileType
        });

        // Generate a presigned URL that the React frontend can use for 60 seconds
        const presignedUrl = await getSignedUrl(r2, command, { expiresIn: 60 });

        return NextResponse.json({
            uploadUrl: presignedUrl,
            uniqueFileName: uniqueFileId,
            message: "Presigned URL generated successfully"
        });

    } catch (error) {
        console.error("Presigned URL generation failed:", error);
        return NextResponse.json(
            { message: "Failed to generate upload URL" },
            { status: 500 }
        );
    }
}
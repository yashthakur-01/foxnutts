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

    try {
        const body = await request.json();
        const { workspace_id } = body;

        if (!workspace_id) {
            return NextResponse.json(
                { message: "Missing required field: workspace_id" },
                { status: 400 }
            );
        }

        const { data: files, error } = await supabase
            .from("files")
            .select("file_id, file_name, status, created_at")
            .eq("workspace_id", workspace_id)
            .order("created_at", { ascending: false });

        if (error) {
            console.error("Error fetching files:", error);
            return NextResponse.json(
                { message: "Failed to fetch files", error: error.message },
                { status: 500 }
            );
        }

        return NextResponse.json({ files: files || [], success: true });

    } catch (error) {
        console.error("Get files endpoint error:", error);
        return NextResponse.json({ message: "Internal server error" }, { status: 500 });
    }
}

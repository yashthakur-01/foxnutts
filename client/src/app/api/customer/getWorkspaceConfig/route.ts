import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/adminClient";
import { getCachedUser } from "../../../../lib/authCache";

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
            return NextResponse.json({ message: "Missing workspace_id", success: false }, { status: 400 });
        }

        const { data: config, error } = await supabase
            .from("workspace")
            .select("*")
            .eq("id", workspace_id)
            .single();

        if (error) {
            console.error("Error fetching workspace config:", error);
            return NextResponse.json({ message: "Failed to fetch workspace config", error: error.message, success: false }, { status: 500 });
        }

        return NextResponse.json({ config, success: true });
    } catch (error: any) {
        console.error("getWorkspaceConfig error:", error);
        return NextResponse.json({ message: "Internal server error", success: false }, { status: 500 });
    }
}

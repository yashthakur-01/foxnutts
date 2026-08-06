import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/adminClient";
import { getCachedUser } from "../../../../lib/authCache";

export async function GET(request: NextRequest) {
    const authHeader = request.headers.get("Authorization");
    const { user, error: customerError } = await getCachedUser(authHeader);
    if (customerError || !user) {
        return NextResponse.json({ message: `Authorization error occurred - ${customerError?.message}`, success: false }, { status: 401 });
    }

    try {
        const { data: workspaces, error } = await supabase
            .from("workspace")
            .select("*")
            .eq("cust_id", user.id)
            .order("created_at", { ascending: false });

        if (error) {
            console.error("Error fetching workspaces:", error);
            return NextResponse.json({ message: "Failed to fetch workspaces", error: error.message, success: false }, { status: 500 });
        }

        return NextResponse.json({ workspaces: workspaces || [], success: true });
    } catch (error: any) {
        console.error("getWorkspaces error:", error);
        return NextResponse.json({ message: "Internal server error", success: false }, { status: 500 });
    }
}

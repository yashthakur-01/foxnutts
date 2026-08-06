import { NextRequest, NextResponse } from "next/server";
import { invalidateAuthUserCache } from "../../../../lib/authCache";

export async function POST(request: NextRequest) {
    const authHeader = request.headers.get("Authorization");
    if (authHeader) {
        invalidateAuthUserCache(authHeader);
    }
    return NextResponse.json({ message: "Logout successful, auth cache cleared", success: true });
}

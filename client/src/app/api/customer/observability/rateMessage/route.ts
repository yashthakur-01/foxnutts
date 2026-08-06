import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../../supabase/adminClient";

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { message_id, rating, feedback_text } = body;

        if (!message_id || (rating !== 1 && rating !== -1)) {
            return NextResponse.json(
                { message: "Missing required fields: message_id and valid rating (1 or -1)", success: false },
                { status: 400 }
            );
        }

        const { data, error } = await supabase
            .from("messages")
            .update({
                rating,
                feedback_text: feedback_text || null
            })
            .eq("id", message_id)
            .select("id, rating, feedback_text");

        if (error) {
            console.error("Error rating message:", error);
            return NextResponse.json(
                { message: "Failed to rate message", error: error.message, success: false },
                { status: 500 }
            );
        }

        return NextResponse.json({
            message: "Rating saved successfully",
            updated_message: data?.[0] || null,
            success: true
        });

    } catch (error) {
        console.error("Rate message endpoint error:", error);
        return NextResponse.json({ message: "Internal server error", success: false }, { status: 500 });
    }
}

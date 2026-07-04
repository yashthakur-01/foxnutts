import { NextRequest, NextResponse } from "next/server";
import supabase from "../../../../supabase/client";

export async function POST(request: NextRequest){

    const body = await request.json();

    const authHeader = request.headers.get("Authorization");

    if(!authHeader){
        return NextResponse.json({message: "Authorization header not found", success:false},{status:400})
    }

    const {data: customer, error: customerError} = await supabase.auth.getUser(authHeader)

    if(customerError){
        return NextResponse.json({message: `Authorization error occured - ${customerError.message}`,success: false},{status:500})
    }

    const cust_id = customer.user.id;

    if(!body.workspace_name || !body.workspace_url){
        return NextResponse.json({message: "missing workspace name or workspace url", success:false}, {status: 400});
    }
    const {workspace_name, workspace_url} = body;
    try{
        const {data: existingWorkspace, error: existingError} = await supabase.from("workspace").select("*").eq("workspace_url", workspace_url).maybeSingle();

        if(existingError){
            return NextResponse.json({message:`Database error occured - ${existingError.cause}`,success: false},{status:500});
        }

        if(existingWorkspace){
            return NextResponse.json({message:"Workspace url slug already exists, try another one"})
        }

        const {data: newWorkspace, error: insertError} = await supabase.from("workspace").insert([{
            workspace_name: workspace_name,
            workspace_url: workspace_url,
            cust_id: cust_id
        }]).select();

        if(insertError){
            return NextResponse.json({message:`Database error occured - ${insertError.message}`,success: false},{status:500});
        }

        return NextResponse.json({message:"Workspace created successfully",success:true, workspace: newWorkspace},{status:200});


    }catch(error){
        return NextResponse.json({message: `Internal server error occured - ${error}`, success:false}, {status: 500})
    }
}
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import multer from "multer";
 
// This function can be marked `async` if using `await` inside
export const proxy = async(request: NextRequest) => {

    const path = request.nextUrl.pathname;

    if(path.startsWith("/api/customer/uploadFile")){

        const storage = multer.memoryStorage();

        const upload = multer({
            storage
        });

    }

}
 
export const config = {
    matcher: '/about/:path*',
}
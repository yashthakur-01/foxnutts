import { S3Client, S3ClientConfigType } from "@aws-sdk/client-s3";
import dotenv from "dotenv";

dotenv.config();

const clientConfig = {
    region: "auto",
    endpoint: process.env.R2_ENDPOINT_URL,
    credentials: {
        accessKeyId: process.env.R2_ACCESS_KEY_ID,
        secretAccessKey: process.env.R2_SECRET_ACCESS_KEY,
    },
} as S3ClientConfigType;

export const r2 = new S3Client(clientConfig);


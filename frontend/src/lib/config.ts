export const config = {
  useMock: process.env.NEXT_PUBLIC_USE_MOCK !== "false",
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
} as const;

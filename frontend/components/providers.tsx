"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TeamProvider } from "./bjt/team-provider";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <TeamProvider>
        {children}
      </TeamProvider>
    </QueryClientProvider>
  );
}

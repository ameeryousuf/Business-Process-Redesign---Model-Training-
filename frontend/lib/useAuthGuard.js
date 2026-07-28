"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/api";

/**
 * Blocks rendering of protected content (and any data-fetching that depends on it)
 * until the client has confirmed an auth token exists. `authed` starts `false` and
 * only flips `true` after the check passes -- callers must not render protected
 * content or fire authenticated requests while `authed` is false, so there is no
 * flash of restricted content and no premature API call for an unauthenticated
 * visitor. Redirects to /login immediately if the check fails.
 */
export function useAuthGuard() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    if (isAuthenticated()) {
      setAuthed(true);
    } else {
      router.replace("/login");
    }
  }, [router]);

  return authed;
}

"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/api";

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

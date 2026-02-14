"use client";

import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/onboarding");
  }, [router]);

  return null;
}

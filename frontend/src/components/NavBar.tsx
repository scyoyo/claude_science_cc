"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function NavBar() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <Link href="/" className="text-xl font-bold text-gray-900">
          Virtual Lab
        </Link>
        <div className="flex items-center gap-6">
          <Link href="/teams" className="text-gray-600 hover:text-gray-900">
            Teams
          </Link>
          <Link href="/settings" className="text-gray-600 hover:text-gray-900">
            Settings
          </Link>

          {!loading && (
            <>
              {user ? (
                <div className="flex items-center gap-3">
                  <Link href="/profile" className="text-sm text-gray-600 hover:text-gray-900">
                    {user.username}
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="text-sm text-red-600 hover:text-red-800"
                  >
                    Logout
                  </button>
                </div>
              ) : (
                <Link
                  href="/login"
                  className="text-sm px-3 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Sign In
                </Link>
              )}
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

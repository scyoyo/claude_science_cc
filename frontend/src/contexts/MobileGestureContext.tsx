"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";

const MOBILE_BREAKPOINT = 768;

interface MobileGestureContextValue {
  isMobile: boolean;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  inputVisible: boolean;
  setInputVisible: (visible: boolean) => void;
  toggleInput: () => void;
}

const MobileGestureContext = createContext<MobileGestureContextValue | null>(null);

export function MobileGestureProvider({ children }: { children: ReactNode }) {
  const [isMobile, setIsMobile] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inputVisible, setInputVisible] = useState(true);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);
  const toggleInput = useCallback(() => setInputVisible((v) => !v), []);

  return (
    <MobileGestureContext.Provider
      value={{
        isMobile,
        sidebarOpen,
        setSidebarOpen,
        toggleSidebar,
        inputVisible,
        setInputVisible,
        toggleInput,
      }}
    >
      {children}
    </MobileGestureContext.Provider>
  );
}

export function useMobileGesture() {
  const ctx = useContext(MobileGestureContext);
  return ctx ?? {
    isMobile: false,
    sidebarOpen: false,
    setSidebarOpen: () => {},
    toggleSidebar: () => {},
    inputVisible: true,
    setInputVisible: () => {},
    toggleInput: () => {},
  };
}

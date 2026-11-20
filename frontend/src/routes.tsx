import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter } from "react-router";

import { ChatPage } from "@/pages/ChatPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

// The chat start page loads eagerly; every other page is split out so the diagram, Stripe and
// checkout code stay off the first paint (quality bar Q2). The start page's small 3D visual is its own chunk.
const LandingPage = lazy(() => import("@/pages/LandingPage").then((m) => ({ default: m.LandingPage })));
const WorkspacePage = lazy(() => import("@/pages/WorkspacePage").then((m) => ({ default: m.WorkspacePage })));
const CartPage = lazy(() => import("@/pages/CartPage").then((m) => ({ default: m.CartPage })));
const ReceiptPage = lazy(() => import("@/pages/ReceiptPage").then((m) => ({ default: m.ReceiptPage })));
const ViewsPage = lazy(() => import("@/pages/ViewsPage").then((m) => ({ default: m.ViewsPage })));

function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="min-h-screen bg-background" aria-busy="true" />}>{children}</Suspense>;
}

// Routes from PLAN §11.5, with the chat as the start page: / is a new conversation, /c/:id an existing one, and
// /about the former landing ("How it works"). /views is the view gallery (example data), not linked from the product.
export const router = createBrowserRouter([
  { path: "/", element: <ChatPage /> },
  { path: "/c/:sessionId", element: <ChatPage /> },
  { path: "/library", element: <ChatPage view="library" /> },
  { path: "/carts", element: <ChatPage view="carts" /> },
  { path: "/receipts", element: <ChatPage view="receipts" /> },
  { path: "/about", element: <Page><LandingPage /></Page> },
  { path: "/run/:id", element: <Page><WorkspacePage /></Page> },
  { path: "/run/:id/cart", element: <Page><CartPage /></Page> },
  { path: "/run/:id/receipt", element: <Page><ReceiptPage /></Page> },
  { path: "/views", element: <Page><ViewsPage /></Page> },
  { path: "*", element: <NotFoundPage /> },
]);

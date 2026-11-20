// Receipt route (PLAN §11.5 E): the frame is C's, the content is D's (components/receipt/).
import { ShoppingCart } from "lucide-react";
import { useEffect } from "react";
import { Link, useParams } from "react-router";

import { Receipt } from "@/components/receipt/Receipt";
import { Button } from "@/components/ui/button";
import { PageShell } from "@/pages/PageShell";

export function ReceiptPage() {
  const { id } = useParams();
  useEffect(() => {
    document.title = "Receipt · Build-to-Cart";
  }, []);
  return (
    <PageShell
      runId={id}
      crumb="Receipt"
      right={
        id ? (
          <Button asChild variant="outline" size="lg">
            <Link to={`/run/${id}/cart`}>
              <ShoppingCart aria-hidden /> Cart
            </Link>
          </Button>
        ) : null
      }
    >
      <div className="mx-auto max-w-[1200px] px-(--b2c-gutter) py-8">{id ? <Receipt runId={id} /> : null}</div>
    </PageShell>
  );
}

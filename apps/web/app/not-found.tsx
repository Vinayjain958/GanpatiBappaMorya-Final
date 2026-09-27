import Link from "next/link";
import { Compass } from "lucide-react";
import { PageContainer } from "@/components/layout/PageContainer";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <PageContainer className="py-16 sm:py-24">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="The page you're looking for doesn't exist or has moved."
        action={
          <Link href="/">
            <Button size="sm" className="rounded-full">
              Back to home
            </Button>
          </Link>
        }
      />
    </PageContainer>
  );
}
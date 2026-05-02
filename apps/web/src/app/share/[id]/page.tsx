"use client";

import { useParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Shield } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function SharePage() {
  const params = useParams();
  const resultId = params.id as string;

  return (
    <div className="container max-w-2xl py-16 text-center space-y-6">
      <Shield className="w-16 h-16 text-primary mx-auto" />
      <h1 className="text-3xl font-bold">Shared Analysis Result</h1>
      <Card>
        <CardContent className="py-8">
          <p className="text-muted-foreground mb-4">
            Result ID: <code className="font-mono text-sm">{resultId}</code>
          </p>
          <p className="text-sm text-muted-foreground mb-6">
            This is a shareable link to a TrustMedia analysis result.
            The full result view is available when the API is running.
          </p>
          <Link href={`/results?video_id=${resultId}`}>
            <Button>View Full Results</Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

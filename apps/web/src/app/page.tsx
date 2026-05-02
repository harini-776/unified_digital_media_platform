import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Shield, Brain, Link2, BarChart3, ArrowRight } from "lucide-react";

const features = [
  {
    icon: <Brain className="w-6 h-6" />,
    title: "Multimodal AI Detection",
    description: "Analyzes faces, voice patterns, lip-sync, and blink behavior using state-of-the-art neural networks.",
  },
  {
    icon: <Link2 className="w-6 h-6" />,
    title: "Blockchain Provenance",
    description: "Immutable on-chain records verify media authenticity with cryptographic proof on Polygon.",
  },
  {
    icon: <Shield className="w-6 h-6" />,
    title: "Trust Score Engine",
    description: "Combines AI signals and blockchain verification into a unified 0-100 trust score.",
  },
  {
    icon: <BarChart3 className="w-6 h-6" />,
    title: "Detailed Analytics",
    description: "Transparent signal breakdown showing exactly why media was flagged or verified.",
  },
];

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="container py-24 md:py-32 space-y-8 text-center">
        <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 text-sm text-primary font-medium">
          <Shield className="w-4 h-4" />
          Deepfake Detection + Blockchain Verification
        </div>
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight max-w-3xl mx-auto">
          Verify Digital Media
          <span className="text-primary"> You Can Trust</span>
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          Upload any video and get an instant trust assessment. Our platform combines
          multimodal AI deepfake detection with blockchain provenance for definitive media verification.
        </p>
        <div className="flex gap-4 justify-center">
          <Link href="/upload">
            <Button size="lg" className="gap-2">
              Analyze a Video <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button variant="outline" size="lg">
              View Dashboard
            </Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="container pb-24 space-y-12">
        <div className="text-center">
          <h2 className="text-3xl font-bold">How It Works</h2>
          <p className="text-muted-foreground mt-2">Two-layer verification for maximum confidence</p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature) => (
            <Card key={feature.title} className="hover:shadow-md transition-shadow">
              <CardContent className="pt-6 space-y-3">
                <div className="p-2 rounded-lg bg-primary/10 w-fit text-primary">{feature.icon}</div>
                <h3 className="font-semibold">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

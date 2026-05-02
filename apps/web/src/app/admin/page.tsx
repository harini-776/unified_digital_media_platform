"use client";

import { useQuery } from "@tanstack/react-query";
import { getVideos } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Film, Activity, HardDrive, Clock } from "lucide-react";

export default function AdminPage() {
  const { data } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => getVideos(1, 1),
  });

  const stats = [
    { label: "Total Videos", value: data?.total ?? 0, icon: <Film className="w-5 h-5" />, color: "text-blue-500" },
    { label: "Analyses Run", value: data?.total ?? 0, icon: <Activity className="w-5 h-5" />, color: "text-green-500" },
    { label: "API Status", value: "Online", icon: <HardDrive className="w-5 h-5" />, color: "text-emerald-500" },
    { label: "Avg. Processing", value: "~45s", icon: <Clock className="w-5 h-5" />, color: "text-amber-500" },
  ];

  return (
    <div className="container py-10 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <p className="text-muted-foreground">System overview and metrics</p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className={stat.color}>{stat.icon}</div>
                <div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                  <p className="text-2xl font-bold">{stat.value}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">System Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Backend</p>
              <p className="font-medium">FastAPI + Celery</p>
            </div>
            <div>
              <p className="text-muted-foreground">AI Runtime</p>
              <p className="font-medium">PyTorch (CPU/Demo Mode)</p>
            </div>
            <div>
              <p className="text-muted-foreground">Blockchain</p>
              <p className="font-medium">Polygon Amoy Testnet</p>
            </div>
            <div>
              <p className="text-muted-foreground">Storage</p>
              <p className="font-medium">Local + IPFS (optional)</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

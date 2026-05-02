"use client";

import { Link2, ExternalLink, Copy, Check, ShieldCheck, ShieldOff } from "lucide-react";
import { truncateHash } from "@/lib/utils";
import type { BlockchainStatus } from "@/types";
import { useState } from "react";

interface BlockchainCardProps {
  blockchain: BlockchainStatus;
  explorerUrl?: string;
}

export function BlockchainCard({ blockchain, explorerUrl }: BlockchainCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const baseExplorer = explorerUrl || process.env.NEXT_PUBLIC_EXPLORER_URL || "https://amoy.polygonscan.com";

  const statusCfg = blockchain.verified
    ? blockchain.match
      ? { label: "On-Chain Verified",  cls: "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20", Icon: ShieldCheck }
      : { label: "Hash Mismatch",      cls: "bg-rose-500/10 text-rose-600 border border-rose-500/20",     Icon: ShieldOff  }
    : { label: "Not Registered",       cls: "bg-muted text-muted-foreground border border-border",          Icon: ShieldOff  };

  return (
    <div className="rounded-2xl border bg-card p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-primary/10 flex items-center justify-center">
            <Link2 className="w-4 h-4 text-primary" />
          </div>
          <span className="text-sm font-semibold">Blockchain Provenance</span>
        </div>
        {blockchain.verified !== null && (
          <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${statusCfg.cls}`}>
            <statusCfg.Icon className="w-3.5 h-3.5" />
            {statusCfg.label}
          </span>
        )}
      </div>

      {blockchain.tx_hash ? (
        <div className="space-y-3">
          <div className="space-y-2">
            {[
              { label: "Transaction", value: truncateHash(blockchain.tx_hash, 8), copyValue: blockchain.tx_hash },
              ...(blockchain.ipfs_cid ? [{ label: "IPFS CID", value: truncateHash(blockchain.ipfs_cid, 8), copyValue: null }] : []),
              ...(blockchain.network  ? [{ label: "Network",  value: blockchain.network, copyValue: null }] : []),
            ].map(({ label, value, copyValue }) => (
              <div key={label} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{label}</span>
                <div className="flex items-center gap-1">
                  <code className="font-mono text-foreground">{value}</code>
                  {copyValue && (
                    <button
                      onClick={() => handleCopy(copyValue)}
                      className="p-1 rounded hover:bg-muted transition-colors"
                    >
                      {copied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3 text-muted-foreground" />}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
          <button
            onClick={() => window.open(`${baseExplorer}/tx/${blockchain.tx_hash}`, "_blank")}
            className="w-full flex items-center justify-center gap-2 text-xs font-medium border rounded-xl py-2.5 hover:bg-accent transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" /> View on Explorer
          </button>
        </div>
      ) : (
        <div className="py-4 text-center space-y-1">
          <p className="text-sm text-muted-foreground">No blockchain record found.</p>
          <p className="text-xs text-muted-foreground/70">Analysis performed using AI signals only.</p>
        </div>
      )}
    </div>
  );
}

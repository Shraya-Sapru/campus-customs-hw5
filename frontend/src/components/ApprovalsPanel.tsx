import type { PendingApproval } from "../types";
import { ApprovalCard } from "./ApprovalCard";

interface Props {
  approvals: PendingApproval[];
  balance: number | null;
  approverName: string;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}

export function ApprovalsPanel({ approvals, balance, approverName, onApprove, onReject }: Props) {
  return (
    <section className="column__block">
      <h3 className="column__subtitle">Pending approvals</h3>
      {approvals.length === 0 && <p className="muted">Nothing waiting on you right now.</p>}
      {approvals.map((approval) => (
        <ApprovalCard
          key={approval.id}
          approval={approval}
          balance={balance}
          approverName={approverName}
          onApprove={() => onApprove(approval.id)}
          onReject={() => onReject(approval.id)}
        />
      ))}
    </section>
  );
}

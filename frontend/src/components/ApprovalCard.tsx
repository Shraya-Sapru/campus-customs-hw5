import type { PendingApproval } from "../types";

interface Props {
  approval: PendingApproval;
  balance: number | null;
  approverName: string;
  onApprove: () => void;
  onReject: () => void;
}

const formatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function ApprovalCard({ approval, balance, approverName, onApprove, onReject }: Props) {
  const after = balance !== null ? balance - approval.amount : null;
  const refLabel = approval.kind === "rent" ? `Lease #${approval.refId}` : `Invoice #${approval.refId}`;

  return (
    <div className="approval-card">
      <div className="approval-card__badge">Needs your approval</div>
      <div className="approval-card__payee">{refLabel}</div>
      {approval.reason && <div className="approval-card__reason">{approval.reason}</div>}
      <div className="approval-card__row">
        <span>Amount</span>
        <strong>{formatter.format(approval.amount)}</strong>
      </div>
      <div className="approval-card__row">
        <span>From</span>
        <strong>{approval.account}</strong>
      </div>
      <div className="approval-card__row">
        <span>Balance after paying</span>
        <strong>{after === null ? "–" : formatter.format(after)}</strong>
      </div>
      <div className="approval-card__row approval-card__row--muted">
        <span>Proposed by</span>
        <span>{approval.proposedBy}</span>
      </div>

      <div className="approval-card__actions">
        <button className="btn btn--gold" disabled={!approverName.trim()} onClick={onApprove}>
          Approve
        </button>
        <button className="btn btn--ghost" onClick={onReject}>
          Reject
        </button>
      </div>
      <p className="approval-card__note">
        {
          "Reject just hides this card here — there's no reject action in the backend, so the proposal stays pending until someone approves it."
        }
      </p>
      {!approverName.trim() && (
        <p className="approval-card__note approval-card__note--warn">
          Enter your name above before approving.
        </p>
      )}
    </div>
  );
}

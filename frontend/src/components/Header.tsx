interface Props {
  offline: boolean;
  live: boolean;
  approverName: string;
  onApproverNameChange: (name: string) => void;
  onReset: () => void;
}

export function Header({ offline, live, approverName, onApproverNameChange, onReset }: Props) {
  return (
    <header className="app-header">
      <div className="app-header__title">
        <span className="app-header__mark">{"\u{1F9E5}"}</span>
        <div>
          <h1>Campus Customs</h1>
          <p>Back Office Desk</p>
        </div>
      </div>

      <div className="app-header__status">
        {offline ? (
          <span className="status-badge status-badge--offline">
            <span className="status-dot status-dot--offline" />
            Backend offline
          </span>
        ) : (
          <span className="status-badge status-badge--online">
            <span className={"status-dot status-dot--online" + (live ? " status-dot--pulse" : "")} />
            {live ? "Live" : "Connected"}
          </span>
        )}
      </div>

      <div className="app-header__approver">
        <label htmlFor="approver-name">Your name</label>
        <input
          id="approver-name"
          type="text"
          placeholder="for approvals"
          value={approverName}
          onChange={(e) => onApproverNameChange(e.target.value)}
        />
      </div>

      <button className="btn btn--danger" onClick={onReset}>
        Reset data
      </button>
    </header>
  );
}

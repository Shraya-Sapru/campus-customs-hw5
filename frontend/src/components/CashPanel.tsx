interface Props {
  displayedBalance: number | null;
  dropping: boolean;
}

const formatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
});

export function CashPanel({ displayedBalance, dropping }: Props) {
  return (
    <div className="cash-panel">
      <div className="cash-panel__label">Checking balance</div>
      <div className={"cash-panel__amount" + (dropping ? " cash-panel__amount--dropping" : "")}>
        {displayedBalance === null ? "–" : formatter.format(displayedBalance)}
      </div>
    </div>
  );
}

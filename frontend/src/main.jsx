import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

function App() {
  const [wallet, setWallet] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("labour_pay_access_token");
    if (!token) return;
    Promise.all([
      fetch(`${API}/wallet`, { headers: { Authorization: `Bearer ${token}` } }),
      fetch(`${API}/wallet/transactions`, { headers: { Authorization: `Bearer ${token}` } }),
    ]).then(async ([w, t]) => {
      if (!w.ok || !t.ok) throw new Error("Unable to load wallet");
      setWallet(await w.json());
      setTransactions(await t.json());
    }).catch(() => setError("Please sign in to view your wallet."));
  }, []);

  return (
    <main className="page">
      <img src="/assets/labour-pay-logo.png" className="logo" alt="Labour Pay" />
      <section className="card">
        <p className="eyebrow">Labour Pay Wallet</p>
        <h1>{wallet ? `₦${Number(wallet.balance).toLocaleString("en-NG", { minimumFractionDigits: 2 })}` : "₦0.00"}</h1>
        <p className="muted">{wallet?.status === "ACTIVE" ? "Wallet active" : "Sign in to continue"}</p>
      </section>
      {error && <p className="error">{error}</p>}
      <section className="card">
        <h2>Recent transactions</h2>
        {transactions.length === 0 ? <p className="muted">No transactions yet.</p> : transactions.slice(0, 10).map((tx) => (
          <div className="row" key={tx.id}>
            <div><strong>{tx.transaction_type}</strong><small>{tx.description}</small></div>
            <strong>₦{Number(tx.amount).toLocaleString("en-NG", { minimumFractionDigits: 2 })}</strong>
          </div>
        ))}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

import { useEffect, useState } from "react";

export default function App() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    fetch("/api/v1/health")
      .then((response) => response.json())
      .then((data) => setStatus(data.status || "unknown"))
      .catch(() => setStatus("offline"));
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>Furniture AI PRO</h1>
      <p>Backend status: {status}</p>
      <p>
        Submit a furniture idea to generate previews and blueprints with the
        AI design services.
      </p>
    </main>
  );
}

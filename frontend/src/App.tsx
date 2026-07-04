import { BrowserRouter, Routes, Route } from "react-router-dom";

function Placeholder({ label }: { label: string }) {
  return <div>{label}</div>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Placeholder label="function-list" />} />
        <Route path="/translate" element={<Placeholder label="translate-page" />} />
        <Route path="/summarize" element={<Placeholder label="summarize-page" />} />
      </Routes>
    </BrowserRouter>
  );
}

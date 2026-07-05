import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { FunctionList } from "./pages/FunctionList";
import { SummarizePage } from "./pages/SummarizePage";
import { TranslatePage } from "./pages/TranslatePage";
import { RecordsPage } from "./pages/RecordsPage";
import { ThemeToggle } from "./components/ThemeToggle";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <header className="app-topbar">
          <Link to="/" className="app-brand">
            <span aria-hidden="true">✨</span>
            AI 文本处理
          </Link>
          <ThemeToggle />
        </header>
        <main className="app-main">
          <Routes>
            <Route path="/" element={<FunctionList />} />
            <Route path="/translate" element={<TranslatePage />} />
            <Route path="/summarize" element={<SummarizePage />} />
            <Route path="/records" element={<RecordsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

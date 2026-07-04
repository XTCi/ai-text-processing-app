import { BrowserRouter, Routes, Route } from "react-router-dom";
import { FunctionList } from "./pages/FunctionList";
import { SummarizePage } from "./pages/SummarizePage";
import { TranslatePage } from "./pages/TranslatePage";
import { ThemeToggle } from "./components/ThemeToggle";

export default function App() {
  return (
    <BrowserRouter>
      <ThemeToggle />
      <Routes>
        <Route path="/" element={<FunctionList />} />
        <Route path="/translate" element={<TranslatePage />} />
        <Route path="/summarize" element={<SummarizePage />} />
      </Routes>
    </BrowserRouter>
  );
}

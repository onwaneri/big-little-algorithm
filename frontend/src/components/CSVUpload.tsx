import { useRef, useState } from "react";
import { parseCSV } from "../api";
import type { Person } from "../types";

interface Props {
  label: string;
  onParsed: (people: Person[]) => void;
}

export default function CSVUpload({ label, onParsed }: Props) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (!file.name.endsWith(".csv")) {
      setStatus("error");
      setMessage("Please upload a .csv file.");
      return;
    }
    setStatus("loading");
    setMessage("");
    try {
      const people = await parseCSV(file);
      onParsed(people);
      setStatus("ok");
      setMessage(`Loaded ${people.length} entries from ${file.name}`);
    } catch (err: unknown) {
      setStatus("error");
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to parse CSV.";
      setMessage(msg);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  const borderColor =
    dragging
      ? "border-indigo-500 bg-indigo-50"
      : status === "ok"
      ? "border-green-400 bg-green-50"
      : status === "error"
      ? "border-red-400 bg-red-50"
      : "border-gray-300 bg-gray-50 hover:bg-gray-100";

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${borderColor}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={onInputChange}
      />
      <p className="font-medium text-gray-700">{label}</p>
      <p className="text-sm text-gray-500 mt-1">
        {status === "loading"
          ? "Uploading…"
          : "Drag & drop or click to choose a .csv file"}
      </p>
      {message && (
        <p
          className={`text-sm mt-2 font-medium ${
            status === "ok" ? "text-green-700" : "text-red-600"
          }`}
        >
          {message}
        </p>
      )}
    </div>
  );
}

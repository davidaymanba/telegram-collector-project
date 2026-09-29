import { screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { FileStatusBadge, StatusBadge, statusColor } from "./StatusBadge";
import { HashText } from "./HashText";
import { EmptyState, ErrorState } from "./States";
import { TagInput } from "./TagInput";
import { Pagination } from "./Pagination";
import { LogTerminal } from "./LogTerminal";
import { ApiError } from "@/lib/api";
import { Inbox } from "lucide-react";
import { shortHash } from "@/lib/utils";

describe("StatusBadge", () => {
  it("renders translated file status in both languages", () => {
    renderWithProviders(<FileStatusBadge status="unclassified" />, { lang: "ar" });
    expect(screen.getByText("غير مصنّف")).toBeInTheDocument();
  });

  it("uses the semantic token for each status", () => {
    expect(statusColor("classified")).toBe("hsl(var(--status-classified) / 1)");
    expect(statusColor("failed", 0.1)).toBe("hsl(var(--status-failed) / 0.1)");
    renderWithProviders(<StatusBadge status="processing" label="Processing" />);
    expect(screen.getByText("Processing").querySelector(".animate-soft-pulse")).not.toBeNull();
  });
});

describe("HashText", () => {
  it("shortens long values and copies the full one", async () => {
    const value = "a".repeat(20) + "b".repeat(44);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    renderWithProviders(<HashText value={value} />);
    expect(screen.getByText(shortHash(value))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith(value);
  });

  it("shows a dash for empty values", () => {
    renderWithProviders(<HashText value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("Empty & error states", () => {
  it("empty state shows title, hint and action", () => {
    renderWithProviders(<EmptyState icon={Inbox} title="No channels" description="Add one" action={<button>Add</button>} />);
    expect(screen.getByText("No channels")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });

  it("error state offers retry", async () => {
    const onRetry = vi.fn();
    renderWithProviders(<ErrorState error={new ApiError(500, "boom")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("network errors get a friendly message", () => {
    renderWithProviders(<ErrorState error={new ApiError(0, "network")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Can't reach the server");
  });
});

describe("TagInput", () => {
  function Harness() {
    const [tags, setTags] = useState(["sql"]);
    return <TagInput value={tags} onChange={setTags} placeholder="Add keyword" />;
  }

  it("adds on Enter/comma, dedupes case-insensitively and removes", async () => {
    renderWithProviders(<Harness />);
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "ERD{Enter}");
    await userEvent.type(input, "SQL,قواعد بيانات،");
    expect(screen.getByText("ERD")).toBeInTheDocument();
    expect(screen.getByText("قواعد بيانات")).toBeInTheDocument();
    expect(screen.getAllByText(/sql/i)).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Remove ERD" }));
    expect(screen.queryByText("ERD")).not.toBeInTheDocument();
    fireEvent.keyDown(input, { key: "Backspace" });
    expect(screen.queryByText("قواعد بيانات")).not.toBeInTheDocument();
  });
});

describe("Pagination", () => {
  it("shows the range and navigates", async () => {
    const onPage = vi.fn();
    renderWithProviders(<Pagination page={2} pages={5} total={120} pageSize={25} onPage={onPage} />);
    expect(screen.getByText("26–50 of 120")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onPage).toHaveBeenCalledWith(3);
  });

  it("disables previous on the first page", () => {
    renderWithProviders(<Pagination page={1} pages={1} total={3} pageSize={25} onPage={() => {}} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});

describe("LogTerminal", () => {
  it("renders levels and fields, always LTR", () => {
    renderWithProviders(
      <LogTerminal
        lines={[
          { seq: 1, ts: "2026-09-01T10:00:00Z", level: "info", event: "download_started", logger: null, fields: { file: "a.pdf" } },
          { seq: 2, ts: "2026-09-01T10:00:01Z", level: "error", event: "download_failed", logger: null, fields: { error: "timeout" } },
        ]}
      />,
      { lang: "ar" },
    );
    const log = screen.getByRole("log");
    expect(log).toHaveAttribute("dir", "ltr");
    expect(log).toHaveTextContent("download_failed");
    expect(log).toHaveTextContent("file=a.pdf");
  });

  it("shows an empty hint", () => {
    renderWithProviders(<LogTerminal lines={[]} />);
    expect(screen.getByText("Start a job to see its logs here.")).toBeInTheDocument();
  });
});

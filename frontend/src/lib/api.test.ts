import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, buildQuery, setCsrfToken } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  setCsrfToken(null);
});

describe("api client", () => {
  it("builds query strings skipping empty values and repeating arrays", () => {
    expect(buildQuery({ q: "x y", page: 2, empty: "", none: undefined, status: ["a", "b"] })).toBe("?q=x+y&page=2&status=a&status=b");
    expect(buildQuery({})).toBe("");
  });

  it("sends the CSRF header on mutations only", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("{}", { status: 200 }));
    setCsrfToken("tok");
    await api.get("/x");
    await api.post("/y", { a: 1 });
    const [, getInit] = fetchMock.mock.calls[0];
    const [, postInit] = fetchMock.mock.calls[1];
    expect((getInit?.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
    expect((postInit?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok");
    expect(postInit?.credentials).toBe("same-origin");
  });

  it("raises ApiError with the server detail and signals 401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Nope" }), { status: 401 }));
    const listener = vi.fn();
    window.addEventListener("tuc:unauthorized", listener);
    await expect(api.get("/files")).rejects.toMatchObject({ status: 401, message: "Nope" });
    expect(listener).toHaveBeenCalled();
    window.removeEventListener("tuc:unauthorized", listener);
  });

  it("maps network failures to status 0", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await api.get("/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(0);
  });
});

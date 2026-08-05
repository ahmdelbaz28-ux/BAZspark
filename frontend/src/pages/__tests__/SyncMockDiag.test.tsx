import { syncApi } from "@/services/fullApi";

const mockGetSyncStatus = vi.fn();
vi.mock("@/services/fullApi", () => ({
  syncApi: {
    getSyncStatus: (...args: unknown[]) => mockGetSyncStatus(...args),
    syncProject: (...args: unknown[]) => vi.fn()(...args),
  },
}));

describe("mock diag", () => {
  it("returns mocked value", async () => {
    mockGetSyncStatus.mockResolvedValue({ status: "synced" });
    const res = await syncApi.getSyncStatus("proj-1");
    expect(res).toEqual({ status: "synced" });
  });
});

const { test, mock } = require("node:test");
const assert = require("node:assert");
const { handleGenericProxy, handleSecureProxy } = require("../proxy");

test("proxy tests", async (t) => {
    // Mock global.fetch
    const originalFetch = global.fetch;
    global.fetch = mock.fn(async (url, opts) => {
        return {
            status: 200,
            text: async () => JSON.stringify({ result: "ok", token_echo: "test_token_123" }),
            headers: {
                get: () => "application/json"
            }
        };
    });

    const env = {
        NIO_KANBAN_API_TOKEN: "test_token_123",
        NIO_APOLLO_APPROVAL_PIN: "9999"
    };

    await t.test("generic proxy missing token", async () => {
        const res = await handleGenericProxy("/api/v1/kanban/tasks", "GET", {}, {});
        assert.equal(res.status, 503);
    });

    await t.test("generic proxy rejects traversal", async () => {
        const res = await handleGenericProxy("/api/v1/kanban/../../secrets", "GET", {}, env);
        assert.equal(res.status, 403);
    });

    await t.test("generic proxy rejects percent encoding", async () => {
        const res = await handleGenericProxy("/api/v1/kanban/%2e%2e/secrets", "GET", {}, env);
        assert.equal(res.status, 403);
    });

    await t.test("generic proxy rejects wrong method", async () => {
        const res = await handleGenericProxy("/api/v1/kanban/tasks", "DELETE", {}, env);
        assert.equal(res.status, 403);
    });

    await t.test("generic proxy rejects POST workers", async () => {
        const res = await handleGenericProxy("/api/v1/workers", "POST", {}, env);
        assert.equal(res.status, 403);
    });

    await t.test("secure proxy missing PIN env", async () => {
        const res = await handleSecureProxy("/api/v1/approvals/issue", "POST", "9999", {}, { NIO_KANBAN_API_TOKEN: "test" });
        assert.equal(res.status, 503);
    });

    await t.test("secure proxy rejects bad PIN and locks out after 5", async () => {
        for (let i = 0; i < 5; i++) {
            const res = await handleSecureProxy("/api/v1/approvals/issue", "POST", "1111", {}, env);
            assert.equal(res.status, 401);
        }
        // 6th attempt even with correct PIN fails
        const resLocked = await handleSecureProxy("/api/v1/approvals/issue", "POST", "9999", {}, env);
        assert.equal(resLocked.status, 429);
    });

    // Reset lock logic requires waiting or manipulating time since it uses Date.now().
    // We can just verify the 429 happens.

    await t.test("token redaction", async () => {
        // Redaction is global state lock out might still be active, we test generic
        const res = await handleGenericProxy("/api/v1/kanban/tasks", "GET", {}, env);
        assert.equal(res.status, 200);
        assert.ok(res.rawText.includes("***REDACTED***"));
        assert.ok(!res.rawText.includes("test_token_123"));
    });

    global.fetch = originalFetch;
});

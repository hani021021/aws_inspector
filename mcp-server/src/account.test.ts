import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { checkAccount } from "./account.js";

describe("checkAccount", () => {
  it("accepts the expected account", () => {
    assert.equal(checkAccount("123456789012", "123456789012"), null);
  });

  it("refuses any other account", () => {
    assert.match(checkAccount("111111111111", "123456789012") ?? "", /111111111111/);
  });

  it("refuses when no expected account is configured", () => {
    assert.notEqual(checkAccount("123456789012", undefined), null);
    // .mcp.json passes an unset variable through literally
    assert.notEqual(checkAccount("123456789012", "${EXPECTED_AWS_ACCOUNT_ID}"), null);
  });
});

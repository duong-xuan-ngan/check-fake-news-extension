import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const dashboardRoot = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("serves the admin dashboard shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Verity/);
  assert.match(html, /Control center/);
  assert.match(html, /Overview/);
});

test("includes all four requested extension product signals", async () => {
  const page = await readFile(new URL("app/page.tsx", dashboardRoot), "utf8");
  const css = await readFile(new URL("app/globals.css", dashboardRoot), "utf8");

  for (const label of [
    "Highlights",
    "Average rating",
    "Extension uninstalls",
    "7-day return rate",
  ]) {
    assert.match(page, new RegExp(label, "i"));
  }

  for (const kind of ["Usage", "Feedback", "Lagging indicator", "Behavioral"]) {
    assert.match(page, new RegExp(kind, "i"));
  }

  assert.match(page, /PREVIEW DATA/);
  assert.match(css, /\.product-signal-grid/);
  assert.match(css, /\.signal-definitions/);
});

test("explains the CRED-1 dataset policy in the sources view", async () => {
  const page = await readFile(new URL("app/page.tsx", dashboardRoot), "utf8");
  assert.match(page, /CRED-1 risk signals active/);
  assert.match(page, /absence never implies trust/i);
  assert.doesNotMatch(page, /category:\s*"MBFC"/);
});

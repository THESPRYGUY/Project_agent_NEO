import { RepoBuilderPanel, RepoBuildOptions } from "../src/neo_agent/ui/repo_builder_panel";

const options: RepoBuildOptions = {
  include_examples: false,
  git_init: false,
  zip: true,
  overwrite: "safe",
};

const profile = { persona: { name: "Atlas" } };

const telemetry: string[] = [];

const api = {
  async validateProfile() {
    return { status: "ok", issues: [] } as const;
  },
  async dryRun() {
    return {
      status: "ok",
      plan: {
        files: [
          { path: "01_README+Directory-Map_v2.json", action: "create", sha256_after: "abc" },
        ],
        inputs_sha256: "hash",
      },
    } as const;
  },
  async build() {
    return {
      status: "ok",
      repo_path: "/tmp/repo",
      zip_path: "/tmp/repo.zip",
      manifest: { manifest_sha: "123", inputs_sha256: "hash" },
      timings_ms: { validate: 1, render: 2, package: 3 },
    } as const;
  },
};

function record(event: { action: string }) {
  telemetry.push(event.action);
}

const panel = new RepoBuilderPanel({ api: api as any, telemetry: record, agentId: "agent-1" });

async function run() {
  panel.setProfile(profile);
  const valid = await panel.validate();
  if (!valid) throw new Error("expected profile validation to succeed");
  if (!panel.isGenerateEnabled()) throw new Error("generate button should be enabled");
  const plan = await panel.dryRun(options);
  if (!plan || plan.files.length !== 1) throw new Error("dry run plan missing");
  const result = await panel.build(options);
  if (result.status !== "ok") throw new Error("build should succeed");
  if (!panel.getResult()) throw new Error("result not stored");
  if (!telemetry.includes("repo:done")) throw new Error("repo:done telemetry missing");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});

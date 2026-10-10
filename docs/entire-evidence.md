# Entire development evidence

Entire evidence documents coding-agent development context linked to source history. It is not TLS verification, an Invaris runtime component, or proof of migration outcomes.

## Verified local checkpoint

The public GitHub repository's initial commit is `166c1b96800345721863c8e1ae6b26f7e8eb86c5` (short form `166c1b9`) with its actual timestamp. No history was backdated.

The Entire Graph plugin's official `v0.4.0` Windows build works. Its doctor and query were verified with no egress for hosted models, remote embeddings, grammar/assets, remote code, network discovery, or telemetry. It queried saved source evidence in `docs/evidence/entire-graph.json`; the result associates the repository snapshot with commit `166c1b9`. The query demonstrates retrieval behavior, not measured token savings or agent-performance improvement.

Entire's seven Codex hooks remain awaiting approval, so automatic hook capture is not claimed. A genuine isolated agent session `01a12796-299f-75b3-961f-52226f14e5b2` was attached using the supported `entire session attach` command. It produced checkpoint `01M4KTRF7AXH7GGZ0YQWQ4NABJ`, linked to initial commit `166c1b9`; the saved checkpoint record is `docs/evidence/entire-checkpoint.json`. This is verified local capture. Hosted Entire GitHub App authentication and an accessible hosted checkpoint link are not yet available. Raw session uploads are not enabled or claimed.

## Durable-evaluation development checkpoint

Session `01a127ab-f2ef-70b1-b740-521377e433ee` implemented and reviewed the durable evaluation changes included in commit `08cb143219d60a2dffab053c5442f39189a1b611`. Supported local capture produced checkpoint `01M4KVMJ6YKJ44M0VJ662YKDW2`; `checkpoint explain` verified its metadata. See `docs/evidence/entire-evaluation-checkpoint.json`. The stored transcript was checked privately against configured API credentials and key-shaped patterns with no matches; this targeted scan is not a universal secret guarantee.

This checkpoint was captured after the implementation commit had already been pushed. No public history was rewritten, and that commit has no checkpoint trailer. This explicit mapping documents the real development context without claiming automatic hook capture or hosted sharing.

## Evidence limits and next steps

The checkpoint records one session; it does not fabricate earlier development history or prove that all implementation changes were captured. The graph query and checkpoint are complementary local artifacts. Keep actual timestamps and distinguish local evidence from hosted sharing.

Before claiming hosted integration, complete the repository owner's Entire GitHub App authorization and verify the resulting hosted checkpoint. If hook capture is enabled later, verify it in an actual supported session and review captured context for secrets before sharing. Submission and public demo publication remain explicitly deferred.

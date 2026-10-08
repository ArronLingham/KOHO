# Submission review and demo

## Before sending

- Resolve every `[AUTHOR: ...]` field in BUILD_LOG and confirm the actual total
  assignment time. Do not turn missing facts into estimates or mistake stories.
- Review README's contract, invariant evidence, and limitations; compare them with
  the code and TEST_PLAN. Personal review judgments belong to the author.
- Check WORKING_NOTES for the clean-checkout command outcomes and verified commit.
- Use the local Git bundle in `dist/` after reviewing its commit identity. It contains
  repository history; local databases, environments, caches, and the personal
  planning packet are excluded. Bundle verification instructions are below.
- If tracked files change after packaging, commit the changes and recreate/verify
  the bundle using `git bundle create dist/move-money-review.bundle main HEAD`.
  Select the project branch explicitly: `--all` also includes app-generated refs.
  The existing bundle does not include later edits.
- Send only after author review and explicit authorization. Nothing has been
  published or sent by this project workflow.

## Inspect a bundle

Replace the bracketed paths with the chosen bundle and a new destination folder:

```sh
git bundle verify [absolute-path-to-bundle]
git clone [absolute-path-to-bundle] [new-review-folder]
```

Then run README's setup, demo, and tests from that clone. Its HEAD must match the
packaged commit recorded in the delivery report. Dependencies are installed by
the setup command; they are not bundled.

## Ten-minute interview demo

1. State the four operations, four rules, integer-cent units, and library scope.
2. Run `scripts/demo.py`: explain account creation, one transfer, unchanged replay,
   conflict/overspend/string rejection, final balances, and matching histories.
3. Run the named competing-transfer test. Show how independent connections prove
   overlap at SQLite's writer boundary and require one domain rejection.
4. Explain the single debit/credit/receipt transaction and persisted retry key.
   Point to a rollback/process-exit test and its assertions.
5. Walk through two or three real commits and the build log. Explain the corrected
   balance description, scope decision, evidence limits, and next hour honestly.

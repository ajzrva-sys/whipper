# Working on whipper

This is Andrew's working guide for changes intended for whipper upstream.
It records Merlijn Wajer's review requests and a few observations from his
public code. It isn't an official project policy.

## Keep the change easy to review

Give each PR one reason to exist. A FreeBSD support change should contain the
platform fixes and their tests. Offset discovery, generated drive tables,
metadata features, and general cleanup should be reviewed separately.

Explain why behavior changes. In particular, justify new fallbacks, optional
dependencies, platform checks, and changes to existing tests. Keep supported
upstream dependencies unless there is evidence that changing them is needed.
Don't substitute a guessed list of device paths for proper discovery.

These points come directly from Merlijn's
[detailed review of #712](https://github.com/whipper-team/whipper/pull/712#issuecomment-5782493638)
and his request for a
[minimal FreeBSD changeset](https://github.com/whipper-team/whipper/pull/712#issuecomment-5782553751).

## Write the description around the behavior

Start with the failure or missing behavior. Explain the change and its reason
in a few short paragraphs. Add a short list when several details need comparing.
Use Andrew's direct, conversational style. Skip promotional wording, long
implementation inventories, and routine Summary/Verification boilerplate.

Include the issue link, a useful example, the checks actually performed, and
any limitation that changes what the result means. Distinguish tests run on a
PR head from tests run on the combined fork. A passing mock isn't a hardware
test. Existing reports are historical evidence, not a new test run.

Merlijn also asked for
[human-to-human discussion](https://github.com/whipper-team/whipper/pull/712#issuecomment-5784688184).
Keep descriptions useful for that discussion. Don't invent personal testing,
reasoning, or authorship claims to make a draft sound more personal.

## Follow the surrounding code

Prefer the smallest change that fixes the demonstrated failure. Reuse existing
helpers and conventions. Avoid moving functions, adding compatibility layers,
or reformatting unrelated code without a concrete need.

This is an inference from a small code sample, not a universal style rule:

- [AnalyzeTask output decoding](https://github.com/whipper-team/whipper/commit/29ee670b7fa6ec7402c774091b893d5414e59bc0)
  fixes one failing operation directly.
- [Python 3 frame division](https://github.com/whipper-team/whipper/commit/47c62a9990b75b7ab2b33a9228c0cfa1d2bdc803)
  changes only the incorrect division and links the issue.
- [Resume support](https://github.com/whipper-team/whipper/commit/6bd389b7b13e15269bf9ef7545f5c301372ac764)
  groups a small set of changes around one user-visible problem.
- [uinput-mapper device names](https://github.com/MerlijnWajer/uinput-mapper/commit/11c8b448f02252f702cb3524ad7daa0753a8a43a)
  follows the existing data flow and naming.
- [tracy path formatting](https://github.com/MerlijnWajer/tracy/commit/01d510ac502f1f21daef1a8dbc164592d35e4fa6)
  gives the concrete failure behind the change.

The whipper code being edited takes precedence over conventions in his other
projects. Keep error handling specific. Preserve track identity and failure
states; missing data must not become a successful verification result.

## Make evidence reproducible

Test the failing path and a nearby working case. Keep regression tests relevant
to the PR. Don't change expected results merely to accept local version labels
or a new implementation's output.

Keep personal absolute paths out of upstream code and docs. Generated data
needs a named source, capture date, checksum, and reproducible generator.
Matching a published offset table doesn't prove each drive was tested; an
offset still needs disc verification. Name technical sources directly.

Keep FreeBSD installation instructions short but sufficient to reproduce a
clean install. Record the OS, Python version, code revision, drive, and disc
when those affect the result. Keep sign-off trailers accurate; never fabricate
someone else's sign-off.

## Andrew's fork workflow

For the September 23, 2026 review, code fixes go to `release/v0.12.0` in
Andrew's fork. PR descriptions may be updated as requested. Leave the upstream
PR branches, review-thread resolution, and merges alone unless Andrew asks
otherwise. Report which fixes exist only in the fork.

This is a task-specific branch choice. Check the current branch and Andrew's
instructions before later work. Preserve unrelated local changes.

# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions, or pull
requests.**

If you discover a security issue in this project, report it privately using GitHub's
[**Report a vulnerability**](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
feature (Security tab → *Report a vulnerability*). This opens a private advisory visible only to the
maintainers.

Please include:

- a description of the issue and its impact,
- steps to reproduce (a minimal proof-of-concept if possible),
- the version / commit affected, and
- any suggested remediation.

We will acknowledge the report, investigate, and coordinate a fix and disclosure timeline with you.

## Scope

This is an **experimental, educational baseline** intended to be forked and run locally. It:

- deploys nothing to your cloud account — a run only makes Amazon Bedrock model calls using *your*
  credentials;
- runs a coding agent with write and shell tools inside a run workspace, contained by a
  `can_use_tool` gate (`harness/gates.py`). Treat any run of untrusted intent files with the same
  caution you would treat running untrusted code, and prefer an isolated environment.

Never commit credentials. `.env` is git-ignored; use it for `AWS_PROFILE` / `AWS_REGION` and model
configuration.

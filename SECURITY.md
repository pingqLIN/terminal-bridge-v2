# Security Policy

## Supported Versions

`tb2` is still early-stage. Security fixes are focused on the newest actively maintained line.

| Version | Supported |
| --- | --- |
| `0.1.x` | Yes |
| `< 0.1.0` | No |

## Reporting a Vulnerability

Please do not open a public issue for a suspected security vulnerability.

Recommended path:

1. Use GitHub private vulnerability reporting if it is enabled on the repository.
2. If that is not available, contact the maintainer privately and include:
   - affected version or commit
   - impact summary
   - reproduction steps
   - proof of concept or logs if safe to share

## What to expect

- Initial acknowledgment target: within 7 days
- Triage and next-step update target: within 14 days
- Public disclosure only after a fix, mitigation, or coordinated advisory plan exists

## Scope notes

Please report issues such as:

- unauthenticated remote control exposure
- privilege escalation through local service defaults
- credential, secret, or token leakage
- unsafe transport behavior that bypasses documented guardrails

Out of scope:

- unsupported local development setups
- self-hosted deployment misconfiguration without a product bug
- feature requests framed as security issues without a concrete exploit path

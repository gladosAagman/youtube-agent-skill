# Security policy

## What this pack touches

Everything runs locally on files you give it. None of the tools make a
network request.
No tool asks for, stores or transmits credentials. Your files under
`~/.claude/youtube/` stay on your machine.

Hardening already in place: calendar files escape and fold every field and
timezone names are validated before use; every numeric input (views, CPM,
impressions, clicks) is validated as finite and in range before any maths.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private vulnerability
reporting on this repository (Security -> Report a vulnerability). Expect an
acknowledgement within a week.

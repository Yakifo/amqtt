# Security Policy

## Supported Versions

Security fixes are provided for the latest minor release line listed below.

| Version | Supported |
| ------- | --------- |
| 0.11.x  | Yes       |
| < 0.11  | No        |

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues,
pull requests, or discussions.

Report vulnerabilities privately through GitHub Security Advisories:

https://github.com/Yakifo/amqtt/security/advisories/new

If you cannot use GitHub Security Advisories, email the report privately to
[support@amqtt.io](mailto:support@amqtt.io).

Include enough detail to reproduce the issue, including affected versions,
configuration, proof-of-concept code if available, and any known mitigations.
Please report in English where possible, and do not include live credentials,
private keys, or third-party personal data in your report.

## Scope

amqtt is an MQTT broker and client library. Reports that are in scope include,
for example:

- Authentication or authorization bypass in the broker or its plugins.
- MQTT packet parsing or protocol-handling flaws that cause crashes, hangs, or
  remote denial of service.
- TLS/transport handling issues that weaken confidentiality or integrity.
- Plugin isolation or privilege-escalation issues.

The following are generally out of scope:

- Misconfiguration of a broker you deploy or operate (for example, running
  without authentication or TLS by choice).
- Vulnerabilities in third-party dependencies — please report those to the
  relevant upstream project, though you are welcome to let us know so we can
  update.
- Denial of service that requires already-authenticated, privileged access, or
  that only affects the reporter's own instance.

If you are unsure whether an issue is in scope, report it privately and let the
maintainers assess it.

## Safe Harbor

We consider security research and vulnerability disclosure conducted in good
faith and in accordance with this policy to be authorized. We will not pursue or
support legal action against reporters for accidental, good-faith violations of
this policy. Please make a good-faith effort to avoid privacy violations,
service disruption, and destruction of data during your research.

## Disclosure Process

Maintainers aim to acknowledge vulnerability reports within 7 days and provide
an initial assessment within 14 days. The expected remediation and coordinated
disclosure timeline is normally up to 90 days, depending on severity, fix
complexity, and reporter coordination. If the timeline needs to be extended, the
maintainers will keep you informed.

Please keep vulnerability details private until a fix or mitigation is available
and the maintainers have coordinated disclosure with you.

### Dual Reporting

Because the project uses GitHub Security Advisories as its reporting mechanism
and follows [CVE CNA Operational Rules 4.2.19 and 4.2.20](https://www.cve.org/ResourcesSupport/AllResources/CNARules),
please do not submit the same vulnerability to any third-party vulnerability
database or other CNA without coordinating with the maintainers first.

Coordination means sharing any existing or planned CVE, GHSA, CNA, or other
vulnerability database submissions and agreeing on affected versions, fixed
versions, advisory text, disclosure timing, and which submission path will be
used.

If you have already requested a CVE assignment or submitted the issue to another
CNA or vulnerability database, include the request or tracking IDs in your
GitHub Security Advisory report.

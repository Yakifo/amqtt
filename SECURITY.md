# Security Policy

## Supported Versions

Security fixes are provided for the current supported release line.

| Version | Supported |
| ------- | --------- |
| 0.11.x  | Yes       |
| < 0.11  | No        |

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues,
pull requests, or discussions.

Report vulnerabilities privately through GitHub Security Advisories:

https://github.com/Yakifo/amqtt/security/advisories/new

Include enough detail to reproduce the issue, including affected versions,
configuration, proof-of-concept code if available, and any known mitigations.

## Disclosure Process

Maintainers aim to acknowledge vulnerability reports within 7 days and provide
an initial assessment within 14 days. The expected remediation and coordinated
disclosure timeline is normally up to 90 days, depending on severity, fix
complexity, and reporter coordination.

Please keep vulnerability details private until a fix or mitigation is available
and the maintainers have coordinated disclosure with you.

### Dual Reporting

After submitting a vulnerability through GitHub Security Advisories, please do
not submit the same vulnerability to CNVD (China National Vulnerability
Database) or another third-party vulnerability database without coordinating
with the maintainers first. Parallel submissions can create duplicate or
conflicting tracking records and may prematurely disclose details before a patch
or mitigation is available.

The project follows [CVE CNA Operational Rules 4.2.19 and 4.2.20](https://www.cve.org/ResourcesSupport/AllResources/CNARules).
Rule 4.2.19 states that CNAs should ask whether requesters have "already
requested an assignment" from another CNA with appropriate scope. Rule 4.2.20
states that CNAs should coordinate with an appropriate Root or CNA-LR to
"minimize duplicate assignments" for publicly disclosed vulnerabilities. These
rules specify that reporters should disclose any prior or parallel CVE, CNVD,
CNA, or vulnerability database submission so the maintainers can defer to, refer
back to, or coordinate with the appropriate assignment authority.

If you have already requested a CVE assignment or submitted the issue to CNVD,
another CNA, or another vulnerability database, include the request or tracking
IDs in your GitHub Security Advisory report. The maintainers will coordinate the
disclosure and CVE workflow from the advisory whenever possible.

To ensure the longevity and stability of this project, here is our our engineering roadmap and release sequence as we prepare for MQTT5 support:

Version | Status | Target Date | Goal | Scope
-- | -- | -- | -- | --
[v0.11.4](https://github.com/Yakifo/amqtt/milestone/9) | in progress | 2026-07-29 | Security Patch | Strictly isolated to the security fix to ensure zero deployment risk for current users.
[v0.12.0](https://github.com/Yakifo/amqtt/milestone/6) | pull request review window | 2026-08-03 | Community Feature Release | Merging and publishing all currently pending and reviewed community Pull Requests. No breaking architectural changes will be included here.
[v1.0.0-rc.1](https://github.com/Yakifo/amqtt/milestone/7) | pull request pending | 2026-08-15 | Multiple Protocol API Pre-release | - Open window for public testing of submodule namespace change from mqtt to mqtt3. Includes clean compatibility shims with explicit runtime deprecation warnings.<br/>- EOL of inconsistent and project-based plugin configuration options (deprecated in `0.11.2)` in favor of yaml config)
[v1.0.0](https://github.com/Yakifo/amqtt/milestone/8) | pull request pending | 2026-10-01 | Multiple Protocol API Release | - Stable release of module layout to enable protocol additions.<br/>- yaml-based configuration, as standard.
[v1.1.0-rc.1](https://github.com/Yakifo/amqtt/milestone/10) | in development | 2026-12-01 | MQTT5 Protocol Pre-release | Open window for public testing of mqtt5 protocol functionality (broker and client), living side-by-size with established mqtt3 implementation.
[v1.1.0](https://github.com/Yakifo/amqtt/milestone/11) | in development | 2027-01-01 | MQTT5 Protocol Release | Stable release of support for both mqtt3 and mqtt5 protocol functionality (broker and client).

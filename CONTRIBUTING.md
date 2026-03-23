# Contributing to DimOS

Thanks for your interest in contributing to DimOS. This guide covers everything you need to get started.

## Quick Start

- See the install guides for [Ubuntu](docs/installation/ubuntu.md), [macOS](docs/installation/osx.md), or [NixOS](docs/installation/nix.md).
- Check [GitHub Issues](https://github.com/dimensionalOS/dimos/issues) for open issues labeled `good first issue`.
- Feature requests and bug reports are also good starting points.
- For larger contributions, open an issue or spec first to discuss the approach before writing code.

## Development Workflow

### Branches

Create a branch from `dev`:

```
<your-name>/<type>/<description>
```

Types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`

Examples: `alex/feat/slam-integration`, `paul/fix/flaky-nav-test`

### Commits

Use [conventional commits](https://www.conventionalcommits.org/):

```
feat: add frontier exploration skill
fix(nav): handle empty costmap edge case
chore: update Open3D to 0.18
```

Include a scope when it helps clarify what changed.

### Code Style, Testing & Technical Reference

See [AGENTS.md](AGENTS.md) for code style rules, testing details, architecture, and project structure.

## Pull Requests

PRs target the `dev` branch. Use the [PR template](.github/pull_request_template.md) and fill in all sections:

1. **Problem** — what you're fixing or adding, with a link to the issue (`Closes #123`)
2. **Solution** — what you changed and why
3. **Breaking Changes** — write "None" if not applicable
4. **How to Test** — must be reproducible

PRs need at least one approving review before merge. Keep PRs focused — one logical change per PR. Minimize pushes to avoid unnecessary CI churn.

### Contributor License Agreement

All contributors must agree to the [CLA](CLA.md). The PR template includes a checkbox for this.

## Getting Help

- Join our [Discord](https://discord.gg/bg4GHPNt) for questions and discussion.
- Open an issue for bugs or feature requests.
- For agent/MCP integration, see [AGENTS.md](AGENTS.md).

## License

DimOS is licensed under [Apache 2.0](LICENSE). By contributing, you agree that your contributions will be licensed under the same terms.

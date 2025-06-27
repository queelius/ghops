# ghops

![PyPI](https://img.shields.io/pypi/v/ghops)
![License](https://img.shields.io/pypi/l/ghops)
![Python Version](https://img.shields.io/pypi/pyversions/ghops)

`ghops` is a powerful command-line tool to streamline the management of your GitHub repositories. Whether you need to clone multiple repositories, keep them updated, or check their statuses, `ghops` provides an intuitive interface with rich, informative outputs.

For full documentation, please visit the [documentation site](https://queelius.github.io/ghops).

## Prerequisites

- **Python 3.7 or higher**
- **Git**: [Download Git](https://git-scm.com/downloads)
- **GitHub CLI (`gh`)**: [Install GitHub CLI](https://cli.github.com/)

> **Note**: `ghops` relies on the GitHub CLI (`gh`) for interacting with GitHub APIs. Make sure you are authenticated using `gh auth login` before using the tool.

## Installation

You can install `ghops` via `pip`:

```bash
pip install ghops
```

Or from source:

```bash
git clone https://github.com/queelius/ghops.git
cd ghops
make install
```

## Quick Start

```bash
# Clone all your repos
ghops get

# Update all repos in the current directory
ghops update -r

# Check the status of all repos
ghops status -r
```

## Contributing

Contributions are welcome! Please see the [Contributing Guide](contributing.md) for more details.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

© 2025 [Alex Towell](https://github.com/queelius)
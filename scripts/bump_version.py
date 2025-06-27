import sys
import toml

def bump_version(bump_type):
    with open("pyproject.toml", "r") as f:
        data = toml.load(f)
    
    version = data["project"]["version"]
    major, minor, patch = map(int, version.split("."))

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        print(f"Invalid bump type: {bump_type}", file=sys.stderr)
        sys.exit(1)

    new_version = f"{major}.{minor}.{patch}"
    data["project"]["version"] = new_version

    with open("pyproject.toml", "w") as f:
        toml.dump(data, f)

    print(new_version)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump_version.py [major|minor|patch]", file=sys.stderr)
        sys.exit(1)
    bump_version(sys.argv[1])

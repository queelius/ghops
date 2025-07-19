#!/bin/bash
# Examples of how to use ghops status streaming output with jq transformations

echo "=== Raw JSONL Output ==="
echo "Each line is a complete JSON object that can be processed immediately:"
python -m ghops status --dir . | head -1
echo

echo "=== Basic Field Extraction ==="
echo "Extract just the repository name and GitHub status:"
python -m ghops status --dir . | jq '{name: .name, on_github: .github.on_github}'
echo

echo "=== Filtering ==="
echo "Show only repositories that are on GitHub:"
python -m ghops status --dir . | jq 'select(.github.on_github == true)'
echo

echo "=== Transformation to Table Format ==="
echo "Create a human-readable table:"
printf "%-20s %-10s %-15s %-15s\n" "REPO" "GITHUB" "LICENSE" "PYPI"
printf "%-20s %-10s %-15s %-15s\n" "----" "------" "-------" "----"
python -m ghops status --dir . | jq -r '[.name, (.github.on_github | if . then "✓" else "✗" end), (.license.name // "None")[0:14], (.pypi_info.package_name // "None")[0:14]] | @tsv' | while IFS=$'\t' read -r name github license pypi; do
    printf "%-20s %-10s %-15s %-15s\n" "$name" "$github" "$license" "$pypi"
done
echo

echo "=== Real-time Progress Monitoring ==="
echo "Show progress as repos are processed (useful for large directories):"
python -m ghops status --dir . | jq -r '"Processing: " + .name + " (" + (.github.on_github | if . then "GitHub" else "Local" end) + ")"'
echo

echo "=== Deployment Readiness Score ==="
echo "Calculate and display deployment readiness:"
python -m ghops status --dir . | jq '{
  repo: .name,
  score: (
    (.github.on_github | if . then 1 else 0 end) +
    ((.license.name != null) | if . then 1 else 0 end) +
    ((.pages_url != null) | if . then 1 else 0 end) +
    ((.pypi_info != null and .pypi_info.version != "Not published") | if . then 1 else 0 end)
  ),
  status: (
    (.github.on_github | if . then 1 else 0 end) +
    ((.license.name != null) | if . then 1 else 0 end) +
    ((.pages_url != null) | if . then 1 else 0 end) +
    ((.pypi_info != null and .pypi_info.version != "Not published") | if . then 1 else 0 end)
  ) | if . >= 3 then "🚀 Ready" elif . >= 2 then "⚠️  Almost" else "❌ Needs work" end
}' | jq -r '"\(.repo): \(.status) (score: \(.score)/4)"'
echo

echo "=== Generate Action Items ==="
echo "Create a todo list based on missing features:"
python -m ghops status --dir . | jq -r '
if (.github.on_github == false) then
  "🔗 " + .name + ": Consider publishing to GitHub"
elif (.license.name == null) then
  "📄 " + .name + ": Add a license file"
elif (.pages_url == null and .github.on_github == true) then
  "🌐 " + .name + ": Enable GitHub Pages"
elif (.pypi_info == null) then
  "📦 " + .name + ": Consider publishing to PyPI"
else
  "✅ " + .name + ": All good!"
end'
echo

echo "=== Export for External Tools ==="
echo "Convert to CSV for importing into spreadsheets:"
echo "name,github_url,license,pypi_package,pages_enabled"
python -m ghops status --dir . | jq -r '[
  .name,
  (.github.url // ""),
  (.license.name // "None"),
  (.pypi_info.package_name // "None"),
  (if .pages_url then "Yes" else "No" end)
] | @csv'
echo

echo "=== Aggregation Example ==="
echo "Collect all results and create summary statistics:"
python -m ghops status --dir . | jq -s '{
  total_repos: length,
  github_repos: map(select(.github.on_github == true)) | length,
  licensed_repos: map(select(.license.name != null)) | length,
  published_packages: map(select(.pypi_info != null and .pypi_info.version != "Not published")) | length,
  pages_enabled: map(select(.pages_url != null)) | length
}'
echo

echo "=== Real-time Alerting ==="
echo "Monitor for problematic repositories:"
python -m ghops status --dir . | jq -r '
if (.status | contains("modified") or contains("untracked")) then
  "🚨 " + .name + " has uncommitted changes: " + .status
elif (.github.on_github == false) then
  "💾 " + .name + " is local-only"
else
  empty
end'

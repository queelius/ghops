#!/bin/bash
# Enhanced ghops list command examples with GitHub metadata

echo "=== Enhanced ghops list Command Examples ==="
echo ""

echo "1. Basic listing with GitHub metadata:"
python -m ghops list --dir . | head -1
echo ""

echo "2. Extract just the essential info:"
python -m ghops list --dir . | jq '{name: .name, language: .github.language, stars: .github.stars}'
echo ""

echo "3. Filter by programming language:"
echo "Python repositories:"
python -m ghops list --dir . | jq 'select(.github.language == "Python")'
echo ""

echo "4. Find popular repositories (>10 stars):"
echo "Popular repos:"
python -m ghops list --dir . | jq 'select(.github.stars > 10)'
echo ""

echo "5. Create a developer dashboard:"
python -m ghops list --dir . | jq '{
  "📁": .name,
  "🌟": .github.stars,
  "🔀": .github.forks, 
  "💻": .github.language,
  "🔒": (if .github.is_private then "Private" else "Public" end),
  "📝": (if .github.description == "" then "No description" else .github.description end)
}'
echo ""

echo "6. Generate a CSV report for spreadsheets:"
echo "name,stars,forks,language,is_fork,is_private"
python -m ghops list --dir . | jq -r '[.name, .github.stars, .github.forks, .github.language, .github.is_fork, .github.is_private] | @csv'
echo ""

echo "7. Find your own projects (not forks):"
echo "Original projects:"
python -m ghops list --dir . | jq 'select(.github.is_fork == false)'
echo ""

echo "8. Language distribution analysis:"
echo "Language breakdown:"
python -m ghops list --dir . | jq -s 'group_by(.github.language) | map({language: .[0].github.language, count: length})'
echo ""

echo "9. Create project cards for documentation:"
python -m ghops list --dir . | jq -r '"## " + .name + "\n- **Language:** " + (.github.language // "Unknown") + "\n- **Stars:** " + (.github.stars | tostring) + "\n- **Forks:** " + (.github.forks | tostring) + "\n- **Type:** " + (if .github.is_fork then "Fork" else "Original" end) + "\n"'
echo ""

echo "10. Repository health score:"
python -m ghops list --dir . | jq '{
  name: .name,
  health_score: (
    (if .github.stars > 0 then 1 else 0 end) +
    (if .github.description != "" then 1 else 0 end) +
    (if .github.language then 1 else 0 end) +
    (if .github.is_fork == false then 1 else 0 end)
  ),
  status: (
    (if .github.stars > 0 then 1 else 0 end) +
    (if .github.description != "" then 1 else 0 end) +
    (if .github.language then 1 else 0 end) +
    (if .github.is_fork == false then 1 else 0 end)
  ) | if . >= 3 then "🚀 Excellent" elif . >= 2 then "✅ Good" else "⚠️ Needs attention" end
}'
echo ""

echo "11. Compare with status command for comprehensive analysis:"
echo "Repository overview (list + status):"
echo "From list command:"
python -m ghops list --dir . | jq '{name: .name, github_stars: .github.stars, language: .github.language}'
echo "From status command:"
python -m ghops status --dir . | jq '{name: .name, git_status: .status, has_pypi: (.pypi_info != null)}'
echo ""

echo "12. Memory usage warning with deduplication:"
python -m ghops list --dir . --dedup | jq '{name: .name, stars: .github.stars, duplicates: .duplicate_count}'

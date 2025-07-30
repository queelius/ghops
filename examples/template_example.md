# Example Custom Template

This is an example of a custom Jinja2 template for ghops export functionality.

## Usage

Save this template with:
```bash
ghops export templates --create my_template
```

Then use it with:
```bash
ghops export list --template my_template --format markdown
```

## Template Example

```jinja2
# {{ title | default("My Repository Collection") }}

Generated on: {{ generated_date }}

Total repositories: {{ total_repos }}
Groups: {{ group_count }}

{% for group_name, repos in groups.items() %}
## {{ group_name | upper }}

This group contains {{ repos | length }} repositories.

{% for repo in repos %}
### 📦 {{ repo.name }}

{% if repo.description %}
> {{ repo.description }}
{% endif %}

**Quick Stats:**
- 🌟 Stars: {{ repo.stars | default(0) }}
- 💻 Language: {{ repo.language | default("Unknown") }}
- 👤 Owner: {{ repo.owner | default("Unknown") }}
- 📄 License: {{ repo.license.name | default("No license") if repo.license else "No license" }}

{% if repo.topics %}
**Topics:** {{ repo.topics | join(" • ") }}
{% endif %}

{% if repo.languages %}
**Language Breakdown:**
{% for lang, stats in repo.languages.items() %}
- {{ lang }}: {{ stats.files }} files ({{ (stats.bytes / 1024) | round(2) }} KB)
{% endfor %}
{% endif %}

{% if repo.url %}
[View Repository →]({{ repo.url }})
{% endif %}

---

{% endfor %}
{% endfor %}

## Summary

Generated {{ total_repos }} repositories across {{ group_count }} groups.
```

## Available Variables

Templates have access to these variables:

- `groups`: Dictionary of grouped repositories
- `generated_date`: Current timestamp
- `total_repos`: Total number of repositories
- `group_count`: Number of groups
- `format`: Export format being used

Each repository object contains:
- `name`: Repository name
- `description`: Repository description
- `language`: Primary language
- `languages`: All languages with file/byte counts
- `stars`: Star count
- `owner`: Repository owner
- `topics`: List of topics
- `tags`: List of tags
- `license`: License information
- `url`: Repository URL
- And many more fields from metadata...

## Jinja2 Features

You can use all Jinja2 features:
- Filters: `{{ text | upper }}`, `{{ list | join(", ") }}`
- Conditionals: `{% if condition %}...{% endif %}`
- Loops: `{% for item in items %}...{% endfor %}`
- Default values: `{{ var | default("fallback") }}`
- Math: `{{ (value / 1024) | round(2) }}`